import { Component, inject, signal, computed, effect, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatService } from '@services/chat.service';
import { DocumentsService } from '@services/documents.service';
import { ConversationsService } from '@services/conversations.service';
import { SettingsService } from '@services/settings.service';
import { ModalService } from '../../../../services/modal.service';
import { MessageBubbleComponent } from '@components/index';
import { LlmSelectionModalComponent } from '@components/modals';

@Component({
  selector: 'app-chat-page',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MessageBubbleComponent,
    LlmSelectionModalComponent
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

  // UI State
  activeTab = signal<'chats' | 'documents'>('chats');
  conversationSearch = signal<string>('');
  theme = signal<'dark' | 'light'>('dark');
  isLlmModalOpen = signal<boolean>(false);

  @ViewChild('scrollContainer') private scrollContainer!: ElementRef;

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

    if (provider === 'ollama') {
      const model = this.settingsService.currentModel();
      return `ollama / ${model || '...'}`;
    }

    return `${provider} / ${prefs.selected_llm_model || '...'}`;
  });

  chatTitle = computed(() => {
    const convId = this.chatService.currentConversationId();
    if (!convId) return '// NEW_CONVERSATION';

    const conv = this.conversationsService.conversations().find(c => c.id === convId);
    return conv ? `// ${conv.title.toUpperCase()}` : '// CONVERSATION';
  });

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
  }

  // Chat Actions
  async handleSendMessage(question: string) {
    const documentIds = this.documentsService.getSelectedIds();
    const conversationId = this.chatService.currentConversationId();

    this.chatService.addUserMessage(question);

    try {
      await this.chatService.sendMessage({
        question,
        document_ids: documentIds,
        conversation_id: conversationId || undefined
      });

      // Note: sendMessage() already adds the assistant message via streaming
      await this.conversationsService.loadConversations();
    } catch (error) {
      console.error('Failed to send message', error);
      this.chatService.addAssistantMessage('Error: Failed to get response.');
    }
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
    if (text && !this.chatService.isLoading()) {
      this.handleSendMessage(text);
      textarea.value = '';
      textarea.style.height = 'auto';
    }
  }
}
