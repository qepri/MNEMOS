import { Injectable, signal, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ApiEndpoints } from '@core/constants/api-endpoints';
import { Conversation, ConversationDetail } from '@core/models';

@Injectable({
  providedIn: 'root'
})
export class ConversationsService {
  private http = inject(HttpClient);

  // State
  conversations = signal<Conversation[]>([]);
  isLoading = signal<boolean>(false);

  async loadConversations(search?: string) {
    this.isLoading.set(true);

    try {
      let params = new HttpParams();
      if (search) {
        params = params.set('search', search);
      }

      const conversations = await firstValueFrom(
        this.http.get<Conversation[]>(ApiEndpoints.CONVERSATIONS, { params })
      );

      this.conversations.set(conversations);
    } catch (error) {
      console.error('Failed to load conversations', error);
    } finally {
      this.isLoading.set(false);
    }
  }

  async loadConversationDetail(id: string): Promise<ConversationDetail> {
    try {
      return await firstValueFrom(
        this.http.get<ConversationDetail>(ApiEndpoints.CONVERSATION_DETAIL(id))
      );
    } catch (error) {
      console.error('Failed to load conversation detail', error);
      throw error;
    }
  }

  async createConversation(title: string): Promise<Conversation> {
    try {
      const conversation = await firstValueFrom(
        this.http.post<Conversation>(ApiEndpoints.CONVERSATIONS, { title })
      );

      this.conversations.update(convs => [conversation, ...convs]);
      return conversation;
    } catch (error) {
      console.error('Failed to create conversation', error);
      throw error;
    }
  }

  async deleteConversation(id: string) {
    try {
      await firstValueFrom(
        this.http.delete(ApiEndpoints.CONVERSATION_DELETE(id))
      );

      this.conversations.update(convs => convs.filter(c => c.id !== id));
    } catch (error) {
      console.error('Failed to delete conversation', error);
      throw error;
    }
  }

  clearConversations() {
    this.conversations.set([]);
  }
}
