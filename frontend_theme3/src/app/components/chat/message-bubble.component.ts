import { Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Message } from '@core/models';

@Component({
  selector: 'app-message-bubble',
  standalone: true,
  imports: [CommonModule],
  template: `
<div class="flex flex-col gap-1 w-full max-w-3xl mx-auto anime-fade-in" [class.items-end]="message().role === 'user'"
    [class.items-start]="message().role === 'assistant'">

    <!-- Content -->
    <div [class]="message().role === 'user'
          ? 'bg-accent text-white px-4 py-3 rounded-2xl rounded-tr-sm message-bubble'
          : 'text-primary message-content'">

        @if (message().role === 'user') {
        <p class="text-sm sm:text-base">{{ message().content }}</p>
        } @else {
        <div class="text-sm sm:text-base prose prose-invert max-w-none" [innerHTML]="safeHtml()"></div>

        @if (message().sources && message().sources!.length > 0) {
          <div class="mt-4 pt-3 border-t border-divider">
            <p class="text-xs font-medium text-secondary mb-2">
              Sources ({{message().sources!.length}})
            </p>
            <div class="space-y-2">
              @for (source of message().sources; track source.document) {
                <div class="text-xs bg-panel p-3 rounded-lg border border-divider">
                  <div class="font-semibold text-primary mb-1">{{ source.document }}</div>
                  <div class="text-secondary line-clamp-2">{{ source.chunk }}</div>
                  <div class="text-secondary opacity-70 mt-1">Score: {{ (source.score * 100).toFixed(1) }}%</div>
                </div>
              }
            </div>
          </div>
        }
        }

    </div>

    <!-- Timestamp -->
    <span class="text-[10px] text-secondary opacity-50 px-1">
        {{ formatTime(message().created_at) }}
    </span>
</div>
  `,
  styles: []
})
export class MessageBubbleComponent {
  message = input.required<Message>();

  formatTime(timestamp: string): string {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  safeHtml() {
    // Simple markdown-like rendering
    const content = this.message().content;
    return content
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`(.*?)`/g, '<code class="bg-input px-1 py-0.5 rounded text-xs">$1</code>')
      .replace(/\n/g, '<br>');
  }
}
