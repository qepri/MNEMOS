import { Injectable, signal, computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ApiEndpoints } from '@core/constants/api-endpoints';
import { Message } from '@core/models';

@Injectable({
    providedIn: 'root'
})
export class ChatService {
    // State Signals
    private _messages = signal<Message[]>([]);
    private _loading = signal<boolean>(false);

    // Computed Signals
    readonly messages = computed(() => this._messages());
    readonly isLoading = computed(() => this._loading());

    private http = inject(HttpClient);

    // This service is deprecated - use the new ChatService from @services instead
    // Keeping for backward compatibility
    clearChat() {
        this._messages.set([]);
    }
}
