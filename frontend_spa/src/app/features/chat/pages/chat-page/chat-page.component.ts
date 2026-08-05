import { Component, inject, signal, computed, effect, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
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
import { ChatEmptyStateComponent } from '../../components/chat-empty-state/chat-empty-state.component';
import { ChatInputComponent } from '../../components/chat-input/chat-input.component';
import { ThemeService } from '@services/theme.service';
import { LlmAvailabilityService } from '@services/llm-availability.service';
import { LlmDormantComponent } from '@shared/components/llm-dormant/llm-dormant.component';

@Component({
  selector: 'app-chat-page',
  standalone: true,
  imports: [
    CommonModule,
    MessageBubbleComponent,
    LlmSelectionModalComponent,
    ImageModalComponent,
    VoiceVisualizerComponent,
    ChatEmptyStateComponent,
    ChatInputComponent,
    LlmDormantComponent
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

  themeService = inject(ThemeService);
  llmAvailability = inject(LlmAvailabilityService);
  isLlmModalOpen = signal<boolean>(false);

  @ViewChild('scrollContainer') private scrollContainer!: ElementRef;

  currentModel = computed(() => {
    const prefs = this.settingsService.chatPreferences();
    if (!prefs) return '...';

    const provider = prefs.llm_provider || 'llamacpp';

    if (provider === 'custom') {
      const connId = prefs.active_connection_id;
      const allConns = this.settingsService.llmConnections();
      const conn = allConns.find((c: any) => c.id === connId);

      const name = conn ? conn.name : 'Custom';
      return `${name} / ${prefs.selected_llm_model || '...'}`;
    }

    if (provider === 'llamacpp') {
      const model = this.settingsService.currentModel();
      return `llamacpp / ${model || '...'}`;
    }

    return `${provider} / ${prefs.selected_llm_model || '...'}`;
  });

  constructor() {
    // Auto-scroll effect
    effect(() => {
      const count = this.chatService.messages().length;
      if (count > 0) {
        setTimeout(() => this.scrollToBottom(), 100);
      }
    });
  }

  // Chat Actions
  async handleSendMessage(payload: { question: string; images: string[]; webSearch: boolean; graphRag: boolean }) {
    if (!payload.question && payload.images.length === 0) return;

    const documentIds = this.documentsService.getSelectedIds();
    const conversationId = this.chatService.currentConversationId();

    // Optimistic UI update
    this.chatService.addUserMessage(payload.question, payload.images);

    try {
      await this.chatService.sendMessage({
        question: payload.question,
        document_ids: documentIds,
        conversation_id: conversationId || undefined,
        web_search: payload.webSearch,
        use_graph_rag: payload.graphRag,
        images: payload.images.length > 0 ? payload.images : undefined
      });

      // Note: sendMessage() already adds the assistant message via streaming
      await this.conversationsService.loadConversations();
    } catch (error) {
      console.error('Failed to send message', error);
      this.chatService.addAssistantMessage('Error: Failed to get response.');
    }
  }







  // UI
  // Edit Message Handler
  handleEditMessage(originalMessage: any, newContent: string) {
    if (this.chatService.isLoading()) return;

    const messages = this.chatService.messages();
    const index = messages.findIndex((m: any) => m.id === originalMessage.id);

    if (index !== -1) {
      // 1. Slice history: keep everything BEFORE this message
      const keptMessages = messages.slice(0, index);
      this.chatService.loadMessages(keptMessages);

      // 2. Resend as if it were a new message
      // Providing defaults for images/webSearch since handled at input level
      this.handleSendMessage({ question: newContent, images: [], webSearch: false, graphRag: false });
    }
  }

  private scrollToBottom() {
    try {
      this.scrollContainer.nativeElement.scrollTop = this.scrollContainer.nativeElement.scrollHeight;
    } catch (err) { }
  }


}
