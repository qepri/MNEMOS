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

    // Hands-Free / Visualizer State
    handsFreeMode = signal<boolean>(false);
    vadState = signal<'idle' | 'listening' | 'processing' | 'speaking'>('idle');

    // Audio Analysis
    private analyser: AnalyserNode | null = null;
    private dataArray: Uint8Array | null = null;
    private microphoneStream: MediaStream | null = null;

    // VAD Settings
    private silenceStart: number = 0;
    private isVadRecording: boolean = false;
    private readonly SILENCE_THRESHOLD = 0.05; // Volume threshold (0-1) - Increased from 0.02
    private readonly SILENCE_DURATION = 3000; // 3 seconds
    private vadInterval: any = null;
    private lastProcessTime: number = 0;

    constructor() {
        this.initBrowserSpeech();
    }

    // ... (initBrowserSpeech remains same) ...

    getAudioFrequencyData(): Uint8Array | null {
        if (this.analyser && this.dataArray) {
            this.analyser.getByteFrequencyData(this.dataArray as any);
            return this.dataArray;
        }
        return null;
    }

    async toggleHandsFree(enable: boolean) {
        this.handsFreeMode.set(enable);

        if (enable) {
            await this.startHandsFree();
        } else {
            this.stopHandsFree();
        }
    }

    private async startHandsFree() {
        try {
            this.microphoneStream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // Setup Audio Context for Analysis
            this.audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
            this.analyser = this.audioContext.createAnalyser();
            const source = this.audioContext.createMediaStreamSource(this.microphoneStream);
            source.connect(this.analyser);

            this.analyser.fftSize = 256;
            const bufferLength = this.analyser.frequencyBinCount;
            this.dataArray = new Uint8Array(bufferLength);

            this.vadState.set('idle');
            this.startVadLoop();

        } catch (e) {
            console.error("Failed to start Hands-Free mode", e);
            this.toastr.error("Could not access microphone for Hands-Free mode.", "Permission Error");
            this.handsFreeMode.set(false);
        }
    }

    private stopHandsFree() {
        this.stopVadLoop();

        if (this.microphoneStream) {
            this.microphoneStream.getTracks().forEach(track => track.stop());
            this.microphoneStream = null;
        }

        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }

        this.analyser = null;
        this.vadState.set('idle');
    }

    // Debug
    currentVolume = signal<number>(0);

    private startVadLoop() {
        if (this.vadInterval) clearInterval(this.vadInterval);

        let recordingStartTime = 0;

        this.vadInterval = setInterval(() => {
            if (!this.analyser || !this.dataArray) return;

            // Don't listen while system is speaking or processing
            if (this.isSpeaking() || this.vadState() === 'processing') return;

            // Cooldown: Don't listen immediately after processing (2s buffer)
            if (Date.now() - this.lastProcessTime < 2000) return;

            this.analyser.getByteFrequencyData(this.dataArray as any);

            // Calculate average volume
            let sum = 0;
            for (let i = 0; i < this.dataArray.length; i++) {
                sum += this.dataArray[i];
            }
            const average = sum / this.dataArray.length;
            const volume = average / 255; // Normalize to 0-1

            this.currentVolume.set(volume);

            if (volume > this.SILENCE_THRESHOLD) {
                // Speech detected
                this.silenceStart = 0;
                if (!this.isVadRecording) {
                    this.startVadRecording();
                    recordingStartTime = Date.now();
                }
            } else {
                // Silence detected
                if (this.isVadRecording) {
                    if (this.silenceStart === 0) {
                        this.silenceStart = Date.now();
                    } else if (Date.now() - this.silenceStart > this.SILENCE_DURATION) {
                        // Silence exceeded duration
                        console.log("Silence detected, stopping...");
                        this.stopVadRecordingAndSubmit();
                    }
                }
            }

            // Safety: Max 10 seconds recording
            if (this.isVadRecording && recordingStartTime > 0 && (Date.now() - recordingStartTime > 10000)) {
                console.log("Max duration exceeded, stopping...");
                this.stopVadRecordingAndSubmit();
                recordingStartTime = 0;
            }

        }, 100); // Check every 100ms
    }

    private stopVadLoop() {
        if (this.vadInterval) clearInterval(this.vadInterval);
        this.vadInterval = null;
        this.isVadRecording = false;
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.stop();
        }
    }

    private startVadRecording() {
        if (!this.microphoneStream) return;

        this.isVadRecording = true;
        this.vadState.set('listening');

        // Re-use MediaRecorder logic but for VAD flow
        this.mediaRecorder = new MediaRecorder(this.microphoneStream);
        this.audioChunks = [];

        this.mediaRecorder.ondataavailable = (event) => {
            this.audioChunks.push(event.data);
        };

        this.mediaRecorder.start();
    }

    private stopVadRecordingAndSubmit() {
        this.isVadRecording = false;
        this.vadState.set('processing'); // Set immediately to block VAD loop
        this.lastProcessTime = Date.now(); // Set timestamp

        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.onstop = async () => {
                // Processing state already set
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                await this.processVadAudio(audioBlob);
            };
            this.mediaRecorder.stop();
        } else {
            this.vadState.set('idle');
        }
    }

    private async processVadAudio(blob: Blob) {
        // 1. Transcribe
        const formData = new FormData();
        formData.append('file', blob, 'recording.webm');

        // Pass model preference if available, else default to efficient one
        const prefs = this.settingsService.chatPreferences();
        if (prefs?.stt_provider === 'groq') {
            // Avoid 'base' warning
            formData.append('model', 'whisper-large-v3-turbo');
        }

        try {
            const res: any = await firstValueFrom(this.http.post('/api/voice/transcribe', formData));
            if (res && res.text) {
                const text = res.text.trim();
                console.log("VAD Transcribed:", text);
                this.lastVadTranscript.set(text); // For debug UI

                const lower = text.toLowerCase();
                // Relaxed Wake Word Check
                // "Zenia", "Xenia", "Zena", "Genius", "Zenith", "Senior" -> Common misinterpretations
                const patterns = ['zenia', 'xenia', 'zena', 'zenya', 'zenith', 'hey zenia'];

                const matched = patterns.some(p => lower.startsWith(p));

                if (matched) {
                    // find which pattern matched to slice correctly? 
                    // simplifying: just look for first space or slice roughly
                    // or just send the whole thing if it's short?
                    // Let's strip the first word if it matches loosely
                    // But prevent hallucinated "Zenia..." if confidence is low (can't check confidence easily)

                    // Simple check: If the text is JUST the wake word, ignore it?
                    // No, "Zenia" might mean "I'm listening".
                    // But if it's "Zenia tell me..." -> "tell me..."

                    const words = text.split(' ');
                    // Remove first word (wake word) based on length or just first token
                    const command = words.slice(1).join(' ').trim();

                    if (command && command.length > 2) { // Ensure command has substance
                        this.transcript.set(command);
                        this.handleCommand(command);
                    } else {
                        // Just wake word?
                        this.videoPlayWakeSound();

                        // If just wake word, maybe we SHOULD stay listening? 
                        // For now, idle.
                        this.vadState.set('idle');
                    }
                } else {
                    console.log("Ignored speech (No Zenia match):", text);
                    this.vadState.set('idle');
                }
            } else {
                this.vadState.set('idle');
            }
        } catch (e: any) {
            console.error("VAD Processing failed", e);
            const msg = e.error?.detail || e.message || "Unknown Error";
            this.lastVadTranscript.set(`Error: ${msg}`);
            this.vadState.set('idle');
        }
    }


    // Helper to interface with ChatPage
    onCommandDetected = signal<string | null>(null);
    lastVadTranscript = signal<string | null>(null);

    private videoPlayWakeSound() {
        // Placeholder or actual sound
    }

    private handleCommand(text: string) {
        this.onCommandDetected.set(text);
        // Reset after a tick so it can trigger again
        setTimeout(() => this.onCommandDetected.set(null), 0);
        // Do NOT reset to idle. Wait for AI response -> speak() -> stopSpeaking() -> idle
        // Safety timeout in case of error/no-response
        setTimeout(() => {
            if (this.vadState() === 'processing' && !this.isSpeaking()) {
                this.vadState.set('idle');
            }
        }, 10000);
    }

    // ... (rest of methods: startListening, stopListening, transcribeApi, etc. - ensure no duplicates) ...

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
        this.vadState.set('idle'); // Resume listening
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
