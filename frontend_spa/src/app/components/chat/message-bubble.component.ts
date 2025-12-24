import { Component, input, signal, inject } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { CommonModule } from '@angular/common';
import { Message, MessageSource } from '@core/models';
import { SourceModalComponent } from '@shared/components/source-modal/source-modal.component';

@Component({
  selector: 'app-message-bubble',
  standalone: true,
  imports: [CommonModule, SourceModalComponent],
  template: `
<div class="flex flex-col gap-1 w-full max-w-3xl mx-auto anime-fade-in"
    [class.message-user]="message().role === 'user'"
    [class.message-assistant]="message().role === 'assistant'"
    [class.items-end]="message().role === 'user'"
    [class.items-start]="message().role === 'assistant'">

    <!-- Content -->
    <div [class]="message().role === 'user'
          ? 'bg-accent text-white px-4 py-3 rounded-2xl rounded-tr-sm message-bubble'
          : 'message-content'"
         [style.color]="message().role === 'assistant' ? 'var(--color-base-content, #ffffff)' : 'inherit'">

        @if (message().role === 'user') {
        <p>{{ message().content }}</p>
        } @else {
        <div [innerHTML]="sanitizedContent" (click)="handleContentClick($event)"></div>

        @if (message().sources && message().sources!.length > 0) {
          <div class="mt-4 pt-3 border-t border-divider">
            <p class="text-xs font-medium text-secondary mb-2">
              Sources ({{message().sources!.length}})
            </p>
            <div class="space-y-2">
              @for (source of message().sources; track source.document) {
                <div
                  class="text-xs bg-panel p-3 rounded-lg border border-divider cursor-pointer hover:bg-hover transition-colors"
                  (click)="openSourceModal(source)">
                  <div class="font-semibold text-primary mb-1 flex items-center justify-between">
                    <span class="truncate pr-2">{{ source.document }}</span>
                    @if (source.location) {
                       <span class="opacity-70 font-normal shrink-0">{{ source.location }}</span>
                    }
                  </div>
                  <div class="text-secondary line-clamp-2">{{ source.text }}</div>
                  <div class="text-secondary opacity-70 mt-1">Score: {{ formatScore(source.score) }}</div>
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

<!-- Source Modal -->
<app-source-modal
  [isOpen]="isModalOpen()"
  [source]="selectedSource()"
  (close)="closeSourceModal()">
</app-source-modal>
  `,
  styles: [`
    .message-user { max-width: 70%; margin-left: auto; }
    .message-assistant { max-width: 100%; }
    .message-bubble { border-radius: 16px; padding: 12px 16px; }
    .message-user .message-bubble { background-color: var(--color-accent); color: var(--color-accent-content); }
    .message-assistant .message-content { color: var(--color-base-content); line-height: 1.7; }

    /* Deep selectors for dynamic content */
    :host ::ng-deep .message-content * { color: inherit; }
    
    :host ::ng-deep .message-content pre {
      background-color: var(--color-panel);
      border: 1px solid var(--color-divider);
      border-radius: 8px;
      padding: 12px;
      overflow-x: auto;
      margin: 12px 0;
    }

    :host ::ng-deep .message-content code {
      background-color: var(--color-input);
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 0.875em;
      font-family: 'Courier New', Courier, monospace;
    }

    :host ::ng-deep .message-content pre code { background: none; padding: 0; }

    :host ::ng-deep .message-content ul,
    :host ::ng-deep .message-content ol { margin-left: 20px; margin-top: 8px; margin-bottom: 8px; }

    :host ::ng-deep .message-content li { margin-bottom: 4px; }

    /* Citations */
    :host ::ng-deep .citation {
      color: var(--color-accent);
      cursor: pointer;
      font-weight: 500;
      text-decoration: underline;
      text-decoration-style: dotted;
      transition: all 0.2s;
    }

    :host ::ng-deep .citation:hover {
      color: var(--color-accent-dark);
      background-color: var(--color-accent-subtle);
      border-radius: 4px;
    }
  `]
})
export class MessageBubbleComponent {
  private sanitizer = inject(DomSanitizer);
  message = input.required<Message>();

  // Modal state
  isModalOpen = signal(false);
  selectedSource = signal<MessageSource | null>(null);

  openSourceModal(source: MessageSource) {
    this.selectedSource.set(source);
    this.isModalOpen.set(true);
  }

  closeSourceModal() {
    this.isModalOpen.set(false);
    this.selectedSource.set(null);
  }

  formatTime(timestamp: string): string {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  formatScore(score: number | undefined): string {
    if (score === undefined || score === null || isNaN(score)) {
      return 'N/A';
    }
    return `${(score * 100).toFixed(1)}%`;
  }

  handleContentClick(event: MouseEvent) {
    const target = event.target as HTMLElement;
    const citation = target.closest('.citation');

    if (citation) {
      const sourceName = citation.getAttribute('data-source');
      if (sourceName && this.message().sources) {
        // Try exact match first, then partial
        const source = this.message().sources?.find(s =>
          s.document === sourceName ||
          s.document.includes(sourceName) ||
          sourceName.includes(s.document)
        );

        if (source) {
          this.openSourceModal(source);
          event.stopPropagation();
        }
      }
    }
  }

  get sanitizedContent(): SafeHtml {
    return this.sanitizer.bypassSecurityTrustHtml(this.safeHtml());
  }

  safeHtml(): string {
    // Simple markdown-like rendering
    const content = this.message().content;

    // First, handle list items (lines starting with *)
    let html = content
      .split('\n')
      .map(line => {
        // Check if line starts with * (list item)
        if (line.trim().startsWith('* ')) {
          return line.replace(/^\s*\*\s/, '<li>') + '</li>';
        }
        return line;
      })
      .join('\n');

    // Wrap consecutive list items in <ul>
    html = html.replace(/((?:<li>.*?<\/li>\n?)+)/g, '<ul class="list-disc ml-5 my-2 space-y-1">$1</ul>');

    // Then handle inline formatting (bold must come before italic to avoid conflicts)
    html = html
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*\n]+?)\*/g, '<em>$1</em>')
      .replace(/`(.*?)`/g, '<code class="bg-input px-1 py-0.5 rounded text-xs">$1</code>')
      .replace(/\[Source:\s*(.*?)\]/g, '<span class="citation" data-source="$1">[Source: $1]</span>')
      .replace(/\n/g, '<br>');

    return html;
  }
}
