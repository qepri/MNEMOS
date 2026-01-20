import { Injectable, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom, Subject, takeUntil } from 'rxjs';
import { ApiEndpoints } from '@core/constants/api-endpoints';
import { ChatRequest, ChatResponse, Message } from '@core/models';
import { SettingsService } from './settings.service';
import { VoiceService } from './voice.service';

@Injectable({
  providedIn: 'root'
})
export class ChatService {
  private http = inject(HttpClient);
  private settingsService = inject(SettingsService);
  private voiceService = inject(VoiceService);

  // State
  messages = signal<Message[]>([]);
  currentConversationId = signal<string | null>(null);
  isLoading = signal<boolean>(false);

  // Cancellation
  private stop$ = new Subject<void>();

  async sendMessage(request: ChatRequest): Promise<ChatResponse | null> {
    this.isLoading.set(true);

    try {
      const response = await firstValueFrom(
        this.http.post<ChatResponse>(ApiEndpoints.CHAT, request).pipe(
          takeUntil(this.stop$)
        )
      ) as ChatResponse;

      // Update current conversation ID
      if (response.conversation_id) {
        this.currentConversationId.set(response.conversation_id);
      }

      // Add assistant message with simulated streaming
      await this.addAssistantMessage(response.answer, response.sources, response.search_queries);

      return response;
    } catch (error) {
      if (this.isLoading()) {
        console.error('Failed to send message', error);
        throw error;
      }
      return null;
    } finally {
      this.isLoading.set(false);
    }
  }

  cancelGeneration() {
    this.stop$.next();
    this.isLoading.set(false);
  }

  loadMessages(messages: Message[]) {
    this.messages.set(messages);
  }

  addUserMessage(content: string, images?: string[]) {
    const userMessage: Message = {
      id: `temp-${Date.now()}`,
      conversation_id: this.currentConversationId() || '',
      role: 'user',
      content,
      images,
      created_at: new Date().toISOString()
    };
    this.messages.update(msgs => [...msgs, userMessage]);
  }

  async addAssistantMessage(content: string, sources: any[] = [], search_queries: string[] = []) {
    const id = `temp-${Date.now()}`;
    const assistantMessage: Message = {
      id,
      conversation_id: this.currentConversationId() || '',
      role: 'assistant',
      content: '', // Start empty
      sources,
      search_queries,
      created_at: new Date().toISOString(),
      status: 'generating'
    };

    // Add empty message first
    this.messages.update(msgs => [...msgs, assistantMessage]);

    // Simulate streaming
    const chunkSize = 15; // Slightly faster chunks for "smoother" feel
    const delay = 5; // Low delay

    for (let i = 0; i < content.length; i += chunkSize) {
      // Check for cancellation
      if (!this.isLoading()) break;

      const chunk = content.slice(i, i + chunkSize);

      this.messages.update(msgs =>
        msgs.map(msg =>
          msg.id === id
            ? { ...msg, content: msg.content + chunk }
            : msg
        )
      );

      await new Promise(resolve => setTimeout(resolve, delay));
    }

    // Mark as completed to reveal sources
    this.messages.update(msgs =>
      msgs.map(msg =>
        msg.id === id
          ? { ...msg, status: 'completed' }
          : msg
      )
    );

    // TTS
    const prefs = this.settingsService.chatPreferences();
    if (prefs?.tts_enabled && this.isLoading()) { // Only speak if not cancelled
      this.voiceService.speak(content);
    }
  }

  clearMessages() {
    this.messages.set([]);
    this.currentConversationId.set(null);
  }

  setConversationId(id: string | null) {
    this.currentConversationId.set(id);
  }
}
