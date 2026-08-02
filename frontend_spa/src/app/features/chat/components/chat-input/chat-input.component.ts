import { Component, ElementRef, ViewChild, computed, effect, inject, signal, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatService } from '@services/chat.service';
import { DocumentsService } from '@services/documents.service';
import { SettingsService } from '@services/settings.service';
import { VoiceService } from '@services/voice.service';
import { ToastrService } from 'ngx-toastr';

@Component({
    selector: 'app-chat-input',
    standalone: true,
    imports: [CommonModule, FormsModule],
    templateUrl: './chat-input.component.html'
})
export class ChatInputComponent {
    // Services
    chatService = inject(ChatService);
    documentsService = inject(DocumentsService);
    settingsService = inject(SettingsService);
    voiceService = inject(VoiceService);
    toastr = inject(ToastrService);

    @Output() sendMessageEvent = new EventEmitter<{ question: string; images: string[]; webSearch: boolean; graphRag: boolean }>();
    @Output() openLlmModal = new EventEmitter<void>();

    // State
    isWebSearchEnabled = signal<boolean>(false);
    isGraphRagEnabled = signal<boolean>(false);
    selectedImages = signal<string[]>([]);
    isDragging = signal<boolean>(false);
    isMenuOpen = signal<boolean>(false);

    @ViewChild('fileInput') fileInput!: ElementRef<HTMLInputElement>;
    @ViewChild('messageInput') messageInput!: ElementRef<HTMLTextAreaElement>;

    // Computed Properties
    visionEnabled = computed(() => {
        const prefs = this.settingsService.chatPreferences();
        if (!prefs) return false;

        const provider = prefs.llm_provider || 'llamacpp';
        const model = (provider === 'llamacpp' ? this.settingsService.currentModel() : prefs.selected_llm_model) || '';

        if (!model) return false;

        if (provider === 'llamacpp') {
            const m = this.settingsService.models()?.models.find(x => x.name === model);
            return !!m?.vision;
        }

        const name = model.toLowerCase();
        if (name.includes('gpt-4o') || name.includes('gpt-4.5') ||
            name.includes('claude-3-5') || name.includes('opus') ||
            name.includes('gemini') || name.includes('vision') ||
            name.includes('scout') || name.includes('maverick')) {
            return true;
        }

        return false;
    });

    currentModel = computed(() => {
        const prefs = this.settingsService.chatPreferences() || {
            llm_provider: 'llamacpp',
            selected_llm_model: ''
        } as any;

        const provider = prefs.llm_provider || 'llamacpp';
        if (provider === 'llamacpp') {
            return `local / ${this.settingsService.currentModel() || '...'}`;
        }

        return `${provider} / ${prefs.selected_llm_model || '...'}`;
    });

    isTtsEnabled = computed(() => {
        return !!this.settingsService.chatPreferences()?.tts_enabled;
    });

    constructor() {
        // Sync Voice Transcript to Input
        effect(() => {
            const text = this.voiceService.transcript();
            if (text && this.messageInput?.nativeElement && !this.voiceService.handsFreeMode()) {
                this.messageInput.nativeElement.value = text;
                this.autoResize(this.messageInput.nativeElement);
            }
        });

        // Listen for Voice Commands (Zenia Mode)
        effect(() => {
            const command = this.voiceService.onCommandDetected();
            if (command) {
                this.sendMessageEvent.emit({
                    question: command,
                    images: this.selectedImages(),
                    webSearch: this.isWebSearchEnabled(),
                    graphRag: this.isGraphRagEnabled()
                });
                this.selectedImages.set([]);
            }
        });

        // Auto-TTS for AI Responses in Hands-Free Mode
        effect(() => {
            const messages = this.chatService.messages();
            const lastMsg = messages[messages.length - 1];

            if (this.voiceService.handsFreeMode() && lastMsg && lastMsg.role === 'assistant') {
                if (this.voiceService.vadState() === 'processing' && !this.voiceService.isSpeaking()) {
                    this.voiceService.speak(lastMsg.content);
                }
            }
        });
    }

    // File Handling
    triggerFileInput() {
        if (!this.visionEnabled()) {
            this.toastr.warning('Current model does not support vision', 'Action not available');
            return;
        }
        this.fileInput.nativeElement.click();
    }

    onFileSelected(event: Event) {
        const input = event.target as HTMLInputElement;
        if (input.files && input.files.length > 0) {
            this.processFile(input.files[0]);
        }
        input.value = '';
    }

    onDragOver(event: DragEvent) {
        event.preventDefault();
        event.stopPropagation();
        if (this.visionEnabled()) {
            this.isDragging.set(true);
        }
    }

    onDragLeave(event: DragEvent) {
        event.preventDefault();
        event.stopPropagation();
        this.isDragging.set(false);
    }

    onDrop(event: DragEvent) {
        event.preventDefault();
        event.stopPropagation();
        this.isDragging.set(false);

        if (!this.visionEnabled()) {
            this.toastr.warning('Current model does not support vision', 'Action not available');
            return;
        }

        if (event.dataTransfer && event.dataTransfer.files.length > 0) {
            this.processFile(event.dataTransfer.files[0]);
        }
    }

    processFile(file: File) {
        if (!file.type.startsWith('image/')) {
            this.toastr.error('Only image files are supported', 'Invalid File');
            return;
        }

        if (file.size > 5 * 1024 * 1024) {
            this.toastr.error('Image size must be less than 5MB', 'File too large');
            return;
        }

        if (this.selectedImages().length >= 5) {
            this.toastr.warning('You can only upload up to 5 images', 'Limit Reached');
            return;
        }

        const reader = new FileReader();
        reader.onload = (e: any) => {
            const base64 = e.target.result as string;
            this.selectedImages.update(imgs => [...imgs, base64]);
        };
        reader.readAsDataURL(file);
    }

    removeImage(index: number) {
        this.selectedImages.update(imgs => imgs.filter((_, i) => i !== index));
    }

    // Menus
    toggleMenu() {
        this.isMenuOpen.update(v => !v);
    }

    closeMenu() {
        this.isMenuOpen.set(false);
    }

    toggleVoiceMode() {
        const newState = !this.voiceService.handsFreeMode();
        this.voiceService.toggleHandsFree(newState);
        if (newState) {
            this.toastr.success("Zenia is listening...", "Voice Mode Active");
        } else {
            this.toastr.info("Voice Mode Disabled");
        }
    }

    toggleVanillaMode() {
        this.isWebSearchEnabled.set(false);
        this.documentsService.clearSelection();
        this.toastr.info('Switched to Chat Only mode', 'Vanilla Mode');
    }

    toggleTts() {
        const current = this.isTtsEnabled();
        this.settingsService.saveChatPreferences({ tts_enabled: !current });
        if (!current) {
            this.toastr.info('Voice responses enabled', 'TTS On');
        } else {
            this.toastr.info('Voice responses disabled', 'TTS Off');
        }
    }

    // Text Input Resizing & Sending
    autoResize(textarea: HTMLTextAreaElement) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 128) + 'px';
    }

    handleKeyDown(event: KeyboardEvent, textarea: HTMLTextAreaElement) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            this.sendMessage(textarea);
        }
    }

    sendMessage(textarea: HTMLTextAreaElement) {
        const text = textarea.value.trim();
        if ((text || this.selectedImages().length > 0) && !this.chatService.isLoading()) {

            this.sendMessageEvent.emit({
                question: text,
                images: this.selectedImages(),
                webSearch: this.isWebSearchEnabled(),
                graphRag: this.isGraphRagEnabled()
            });

            this.selectedImages.set([]);
            textarea.value = '';
            textarea.style.height = 'auto';
        }
    }

    stopGeneration() {
        this.chatService.cancelGeneration();
        this.toastr.info('Request cancelled', 'Stopped');
    }
}
