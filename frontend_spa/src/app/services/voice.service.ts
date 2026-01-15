import { Injectable, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { SettingsService } from './settings.service';
import { firstValueFrom } from 'rxjs';

// Type definitions for Web Speech API
declare var webkitSpeechRecognition: any;
declare var SpeechRecognition: any;

import { ToastrService } from 'ngx-toastr';

@Injectable({
    providedIn: 'root'
})
export class VoiceService {
    private http = inject(HttpClient);
    private settingsService = inject(SettingsService);
    private toastr = inject(ToastrService);

    isListening = signal<boolean>(false);
    isSpeaking = signal<boolean>(false);
    transcript = signal<string>('');

    // Internal state
    private recognition: any;
    private mediaRecorder: MediaRecorder | null = null;
    private audioChunks: Blob[] = [];
    private audioContext: AudioContext | null = null;
    private currentAudio: HTMLAudioElement | null = null;

    constructor() {
        this.initBrowserSpeech();
    }

    private initBrowserSpeech() {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false; // Stop after one sentence? Or true? Usually false for chat input is easier.
            this.recognition.interimResults = true;
            this.recognition.lang = 'en-US';

            this.recognition.onstart = () => this.isListening.set(true);
            this.recognition.onend = () => {
                if (this.settingsService.chatPreferences()?.stt_provider === 'browser') {
                    this.isListening.set(false);
                }
            };

            this.recognition.onresult = (event: any) => {
                let interimTranscript = '';
                let finalTranscript = '';

                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        finalTranscript += event.results[i][0].transcript;
                    } else {
                        interimTranscript += event.results[i][0].transcript;
                    }
                }
                // Update signal with current mostly-final text or interim if needed
                // For chat input, we might want to just append final? 
                // Or show interim.
                // Let's just set transcript to the final + interim for now
                if (finalTranscript || interimTranscript) {
                    this.transcript.set(finalTranscript + interimTranscript);
                }
            };

            this.recognition.onerror = (event: any) => {
                console.error('Speech recognition error', event.error);
                this.isListening.set(false);

                let message = 'An error occurred with voice recognition.';
                let title = 'Voice Error';

                if (event.error === 'network') {
                    message = 'Network error: Please check your internet connection.';
                    title = 'Connection Error';
                } else if (event.error === 'not-allowed') {
                    message = 'Microphone access denied. Please allow microphone permissions.';
                    title = 'Permission Error';
                } else if (event.error === 'no-speech') {
                    return; // Ignore no-speech, user just didn't say anything
                }

                this.toastr.error(message, title);
            };
        }
    }

    async startListening() {
        this.transcript.set('');
        const prefs = this.settingsService.chatPreferences();
        const provider = prefs?.stt_provider || 'browser';

        if (provider === 'browser') {
            if (this.recognition) {
                try {
                    this.recognition.start();
                } catch (e) {
                    console.warn("Recognition already started or failed", e);
                }
            } else {
                alert("Browser does not support Speech Recognition.");
            }
        } else {
            // API-based providers (openai, groq, deepgram) use MediaRecorder
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                this.mediaRecorder = new MediaRecorder(stream);
                this.audioChunks = [];

                this.mediaRecorder.ondataavailable = (event) => {
                    this.audioChunks.push(event.data);
                };

                this.mediaRecorder.onstop = async () => {
                    this.isListening.set(false);
                    const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                    // Send to backend
                    await this.transcribeApi(audioBlob);
                    // Stop tracks
                    stream.getTracks().forEach(track => track.stop());
                };

                this.mediaRecorder.start();
                this.isListening.set(true);
            } catch (err) {
                console.error("Microphone access denied or error", err);
                this.toastr.error("Could not access microphone.", "Permission Error");
            }
        }
    }

    stopListening() {
        const prefs = this.settingsService.chatPreferences();
        const provider = prefs?.stt_provider || 'browser';

        if (provider === 'browser') {
            if (this.recognition) this.recognition.stop();
        } else {
            if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
                this.mediaRecorder.stop();
            }
        }
    }

    private async transcribeApi(blob: Blob) {
        const formData = new FormData();
        formData.append('file', blob, 'recording.webm');

        try {
            const res: any = await firstValueFrom(this.http.post('/api/voice/transcribe', formData));
            if (res && res.text) {
                this.transcript.set(res.text);
            }
        } catch (e) {
            console.error('Transcription failed', e);
            this.toastr.error('Failed to transcribe audio.', 'Transcription Error');
        }
    }

    async speak(text: string) {
        if (!text) return;

        // Stop any current speech
        this.stopSpeaking();

        const prefs = this.settingsService.chatPreferences();
        const provider = prefs?.tts_provider || 'browser';

        this.isSpeaking.set(true);

        if (provider === 'browser') {
            const utterance = new SpeechSynthesisUtterance(text);
            // Optional: select voice if we want to support browser voice selection?
            // For now, default.
            utterance.onend = () => this.isSpeaking.set(false);
            utterance.onerror = () => this.isSpeaking.set(false);
            window.speechSynthesis.speak(utterance);
        } else {
            // API-based providers (openai, groq, deepgram)
            try {
                // Call backend
                // Response is blob
                const response = await firstValueFrom(this.http.post('/api/voice/synthesize', { text }, { responseType: 'blob' }));

                const url = URL.createObjectURL(response);
                this.currentAudio = new Audio(url);
                this.currentAudio.onended = () => {
                    this.isSpeaking.set(false);
                    URL.revokeObjectURL(url);
                };
                this.currentAudio.play();
            } catch (e) {
                console.error("TTS failed", e);
                this.toastr.error("Failed to synthesize speech.", "TTS Error");
                this.isSpeaking.set(false);
            }
        }
    }

    stopSpeaking() {
        if (window.speechSynthesis.speaking) {
            window.speechSynthesis.cancel();
        }
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }
        this.isSpeaking.set(false);
    }

    playMessageAudio(messageId: string) {
        // Stop any current speech
        this.stopSpeaking();
        this.isSpeaking.set(true);

        const url = `/api/voice/message/${messageId}/audio`;
        this.currentAudio = new Audio(url);

        this.currentAudio.onended = () => {
            this.isSpeaking.set(false);
            this.currentAudio = null;
        };

        this.currentAudio.onerror = (e) => {
            console.error("Audio playback failed", e);
            this.isSpeaking.set(false);
            this.toastr.error("Could not play audio for this message", "Playback Error");
        };

        this.currentAudio.play().catch(err => {
            console.error("Play failed", err);
            this.isSpeaking.set(false);
        });
    }
}
