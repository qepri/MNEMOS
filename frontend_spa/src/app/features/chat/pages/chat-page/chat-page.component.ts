import { Component, inject, signal, computed, effect, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatService } from '@services/chat.service';
import { DocumentsService } from '@services/documents.service';
import { ConversationsService } from '@services/conversations.service';
import { SettingsService } from '@services/settings.service';
import { VoiceService } from '@services/voice.service';
import { ModalService } from '../../../../services/modal.service';
import { MessageBubbleComponent, ImageModalComponent } from '@components/index';
import { LlmSelectionModalComponent } from '@components/modals';
import { VoiceVisualizerComponent } from '@components/voice-visualizer/voice-visualizer.component';
import { ToastrService } from 'ngx-toastr';

@Component({
  selector: 'app-chat-page',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MessageBubbleComponent,
    LlmSelectionModalComponent,
    ImageModalComponent,
    VoiceVisualizerComponent
  ],
  templateUrl: './chat-page.component.html',
  styleUrl: './chat-page.component.css'
})
export class ChatPage {
  // Services
  chatService = inject(ChatService);
  documentsService = inject(DocumentsService);
  conversationsService = inject(ConversationsService);
  settingsService = inject(SettingsService);
  modalService = inject(ModalService);
  toastr = inject(ToastrService);
  voiceService = inject(VoiceService); // Inject VoiceService

  // UI State
  activeTab = signal<'chats' | 'documents'>('chats');
  conversationSearch = signal<string>('');
  theme = signal<'dark' | 'light'>('dark');
  isLlmModalOpen = signal<boolean>(false);
  isWebSearchEnabled = signal<boolean>(false);
  isGraphRagEnabled = signal<boolean>(false); // New Graph RAG Toggle
  selectedImages = signal<string[]>([]);
  isDragging = signal<boolean>(false);
  isMenuOpen = signal<boolean>(false);

  toggleMenu() {
    this.isMenuOpen.update(v => !v);
  }

  closeMenu() {
    this.isMenuOpen.set(false);
  }

  @ViewChild('scrollContainer') private scrollContainer!: ElementRef;
  @ViewChild('fileInput') fileInput!: ElementRef<HTMLInputElement>;
  @ViewChild('messageInput') messageInput!: ElementRef<HTMLTextAreaElement>; // ViewChild for input

  // Computed
  filteredConversations = computed(() => {
    const search = this.conversationSearch().toLowerCase();
    if (!search) return this.conversationsService.conversations();

    return this.conversationsService.conversations().filter(c =>
      c.title.toLowerCase().includes(search)
    );
  });

  selectedDocCount = computed(() => this.documentsService.selectedCount());
  selectedDocLabel = computed(() => {
    const count = this.selectedDocCount();
    return count > 0 ? `${count}_DOCS_SELECTED` : 'NO_DOCS_SELECTED';
  });

  currentModel = computed(() => {
    const prefs = this.settingsService.chatPreferences();
    if (!prefs) return '...';

    const provider = prefs.llm_provider || 'ollama';

    if (provider === 'custom') {
      const connId = prefs.active_connection_id;
      const allConns = this.settingsService.llmConnections();
      const conn = allConns.find(c => c.id === connId);

      const name = conn ? conn.name : 'Custom';
      return `${name} / ${prefs.selected_llm_model || '...'}`;
    }

    if (provider === 'ollama') {
      const model = this.settingsService.currentModel();
      return `ollama / ${model || '...'}`;
    }

    return `${provider} / ${prefs.selected_llm_model || '...'}`;
  });

  visionEnabled = computed(() => {
    const prefs = this.settingsService.chatPreferences();
    if (!prefs) return false;

    const provider = prefs.llm_provider || 'ollama';
    const model = (provider === 'ollama' ? this.settingsService.currentModel() : prefs.selected_llm_model) || '';

    if (!model) return false;

    // Check Ollama capability flag
    if (provider === 'ollama') {
      const m = this.settingsService.models()?.models.find(x => x.name === model);
      return !!m?.vision;
    }

    // Check Cloud patterns (Hardcoded for now matching modal)
    const name = model.toLowerCase();
    // Known vision models
    if (name.includes('gpt-4o') || name.includes('gpt-4.5') ||
      name.includes('claude-3-5') || name.includes('opus') ||
      name.includes('gemini') || name.includes('vision') ||
      name.includes('scout') || name.includes('maverick')) {
      return true;
    }

    return false;
  });

  isVanillaMode = computed(() => {
    return !this.isWebSearchEnabled() && this.documentsService.selectedCount() === 0;
  });

  toggleVanillaMode() {
    this.isWebSearchEnabled.set(false);
    this.documentsService.clearSelection();
    this.toastr.info('Switched to Chat Only mode', 'Vanilla Mode');
  }

  chatTitle = computed(() => {
    const convId = this.chatService.currentConversationId();
    if (!convId) return '// NEW_CONVERSATION';

    const conv = this.conversationsService.conversations().find(c => c.id === convId);
    return conv ? `// ${conv.title.toUpperCase()}` : '// CONVERSATION';
  });

  isTtsEnabled = computed(() => {
    return !!this.settingsService.chatPreferences()?.tts_enabled;
  });

  toggleTts() {
    const current = this.isTtsEnabled();
    this.settingsService.saveChatPreferences({ tts_enabled: !current });
    if (!current) {
      this.toastr.info('Voice responses enabled', 'TTS On');
    } else {
      this.toastr.info('Voice responses disabled', 'TTS Off');
    }
  }

  constructor() {
    // Auto-scroll effect
    effect(() => {
      const count = this.chatService.messages().length;
      if (count > 0) {
        setTimeout(() => this.scrollToBottom(), 100);
      }
    });

    // Load theme
    const saved = localStorage.getItem('theme') as 'dark' | 'light';
    if (saved) this.theme.set(saved);
    effect(() => {
      const themeName = this.theme() === 'dark' ? 'mnemos-dark' : 'mnemos-light';
      document.documentElement.setAttribute('data-theme', themeName);
      localStorage.setItem('theme', this.theme());
    });

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
        this.handleSendMessage(command);
      }
    });

    // Auto-TTS for AI Responses in Hands-Free Mode
    effect(() => {
      const messages = this.chatService.messages();
      const lastMsg = messages[messages.length - 1];

      if (this.voiceService.handsFreeMode() && lastMsg && lastMsg.role === 'assistant') {
        // We need to check if this is a NEW message or if we just turned on the mode.
        // A simple check is if we are currently 'processing' or if the message is very recent?
        // Ideally, we replicate 'isSpeaking' logic or just trust that speaking idempotent-ish

        // Better check: Only speak if not already speaking and content exists
        // AND if the voice service state is expecting a response (processing)
        // This prevents reading old history when toggling mode.

        if (this.voiceService.vadState() === 'processing' && !this.voiceService.isSpeaking()) {
          this.voiceService.speak(lastMsg.content);
        }
      }
    });
  }

  toggleRecording() {
    if (this.voiceService.isListening()) {
      this.voiceService.stopListening();
    } else {
      this.voiceService.startListening();
    }
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

  // Chat Actions
  async handleSendMessage(question: string) {
    if (!question && this.selectedImages().length === 0) return;

    const documentIds = this.documentsService.getSelectedIds();
    const conversationId = this.chatService.currentConversationId();
    const images = this.selectedImages(); // Capture images

    // Optimistic UI update
    this.chatService.addUserMessage(question, images);

    // Clear input state immediately
    this.selectedImages.set([]);

    try {
      await this.chatService.sendMessage({
        question,
        document_ids: documentIds,
        conversation_id: conversationId || undefined,
        web_search: this.isWebSearchEnabled(),
        use_graph_rag: this.isGraphRagEnabled(),
        images: images.length > 0 ? images : undefined
      });

      // Note: sendMessage() already adds the assistant message via streaming
      await this.conversationsService.loadConversations();
    } catch (error) {
      console.error('Failed to send message', error);
      this.chatService.addAssistantMessage('Error: Failed to get response.');
    }
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
      const file = input.files[0];
      this.processFile(file);
    }
    input.value = ''; // Reset
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
      const file = event.dataTransfer.files[0];
      this.processFile(file);
    }
  }

  processFile(file: File) {
    if (!file.type.startsWith('image/')) {
      this.toastr.error('Only image files are supported', 'Invalid File');
      return;
    }

    if (file.size > 5 * 1024 * 1024) { // 5MB
      this.toastr.error('Image size must be less than 5MB', 'File too large');
      return;
    }

    if (this.selectedImages().length >= 5) {
      this.toastr.warning('You can only upload up to 5 images', 'Limit Reached');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e: any) => {
      const base64 = e.target.result as string; // data:image/jpeg;base64,...
      this.selectedImages.update(imgs => [...imgs, base64]);
    };
    reader.readAsDataURL(file);
  }

  removeImage(index: number) {
    this.selectedImages.update(imgs => imgs.filter((_, i) => i !== index));
  }

  // Conversation Actions
  async handleSelectConversation(id: string) {
    try {
      const detail = await this.conversationsService.loadConversationDetail(id);
      this.chatService.loadMessages(detail.messages);
      this.chatService.setConversationId(id);

      this.documentsService.clearSelection();
      detail.related_document_ids.forEach(docId => {
        this.documentsService.toggleDocument(docId);
      });
    } catch (error) {
      console.error('Failed to load conversation', error);
    }
  }

  async handleDeleteConversation(id: string) {
    if (!confirm('¿Eliminar esta conversación?')) return;
    await this.conversationsService.deleteConversation(id);
    if (this.chatService.currentConversationId() === id) {
      this.handleNewChat();
    }
  }

  handleNewChat() {
    this.chatService.clearMessages();
    this.chatService.setConversationId(null);
  }

  // Edit Message Handler
  handleEditMessage(originalMessage: any, newContent: string) {
    if (this.chatService.isLoading()) return;

    const messages = this.chatService.messages();
    const index = messages.findIndex(m => m.id === originalMessage.id);

    if (index !== -1) {
      // 1. Slice history: keep everything BEFORE this message
      const keptMessages = messages.slice(0, index);
      this.chatService.loadMessages(keptMessages);

      // 2. Resend as if it were a new message
      this.handleSendMessage(newContent);
    }
  }

  // Document Actions
  handleToggleDocument(id: string) {
    this.documentsService.toggleDocument(id);
  }

  async handleDeleteDocument(id: string) {
    if (!confirm('¿Eliminar este documento?')) return;
    await this.documentsService.removeDocument(id);
  }

  // UI
  switchTab(tab: 'chats' | 'documents') {
    this.activeTab.set(tab);
  }

  toggleTheme() {
    this.theme.update(t => t === 'dark' ? 'light' : 'dark');
  }

  private scrollToBottom() {
    try {
      this.scrollContainer.nativeElement.scrollTop = this.scrollContainer.nativeElement.scrollHeight;
    } catch (err) { }
  }

  // Input handlers
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
    // Allow sending if text OR images
    if ((text || this.selectedImages().length > 0) && !this.chatService.isLoading()) {
      this.handleSendMessage(text);
      textarea.value = '';
      textarea.style.height = 'auto';
    }
  }

  stopGeneration() {
    this.chatService.cancelGeneration();
    this.toastr.info('Request cancelled', 'Stopped');
  }
}
