import { Component, input, signal, inject, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Message, MessageSource } from '@core/models';
import { SourceModalComponent } from '@shared/components/source-modal/source-modal.component';
import { MarkdownDisplayComponent } from '../markdown/markdown-display.component';
import { ModalService } from '@services/modal.service';
import { ApiEndpoints } from '@core/constants/api-endpoints';

import { VoiceService } from '@services/voice.service';

import { GraphVisualizerComponent } from '@shared/components/graph-visualizer/graph-visualizer.component';
import { Router } from '@angular/router';

@Component({
  selector: 'app-message-bubble',
  standalone: true,
  imports: [CommonModule, FormsModule, SourceModalComponent, MarkdownDisplayComponent, GraphVisualizerComponent],
  template: `
    <div class="flex flex-col gap-1 w-full max-w-3xl mx-auto anime-fade-in group"
      [class.message-user]="message().role === 'user'"
      [class.message-assistant]="message().role === 'assistant'"
      [class.items-end]="message().role === 'user'"
      [class.items-start]="message().role === 'assistant'">

      <!-- Content -->
      <div [class]="message().role === 'user' 
        ? 'bg-accent text-white px-4 py-3 rounded-2xl rounded-tr-sm message-bubble relative' 
        : 'message-content w-full'"
        [style.color]="message().role === 'assistant' ? 'var(--color-base-content, #ffffff)' : 'inherit'">
        
        @if (message().role === 'user') {
          <!-- Display Images -->
          @if (message().images && message().images!.length > 0) {
            <div class="flex flex-wrap gap-2 mb-2">
              @for (img of message().images; track $index) {
                <img [src]="img" 
                     alt="Uploaded Image" 
                     class="max-w-full h-auto rounded-lg max-h-60 object-contain border border-white/20 cursor-pointer hover:opacity-90 transition-opacity"
                     (click)="openImage($index, message().images)">
              }
            </div>
          }
          @if (isEditing()) {
            <div class="flex flex-col gap-2 min-w-[300px]">
              <textarea 
                [(ngModel)]="editContent" 
                rows="3"
                class="w-full bg-white/10 text-white placeholder-white/50 border border-white/20 rounded-lg p-2 focus:outline-none focus:ring-1 focus:ring-white/50 text-sm resize-none">
              </textarea>
              <div class="flex justify-end gap-2">
                <button (click)="cancelEdit()" class="px-3 py-1.5 text-xs font-medium text-white/80 hover:bg-white/10 rounded-lg transition-colors">
                  Cancel
                </button>
                <button (click)="submitEdit()" class="px-3 py-1.5 text-xs font-medium bg-white text-accent hover:bg-white/90 rounded-lg transition-colors">
                  Send
                </button>
              </div>
            </div>
          } @else {
            <p class="whitespace-pre-wrap">{{ message().content }}</p>
          }
        } @else {
          <!-- Helper Component for Markdown Rendering -->
          <app-markdown-display 
            [content]="message().content" 
            (citationClick)="handleCitation($event)">
          </app-markdown-display>

          @if (message().search_queries && message().search_queries!.length > 0) {
            <div class="mt-4 pt-3 border-t border-divider">
              <p class="text-xs font-medium text-secondary mb-2 flex items-center gap-1">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m16.24 7.76-2.12 6.36-6.36 2.12 2.12-6.36 6.36-2.12z"/></svg>
                Web Search Queries used:
              </p>
              <div class="flex flex-wrap gap-2">
                @for (query of message().search_queries; track query) {
                  <span class="badge badge-ghost badge-sm text-xs font-normal h-auto py-1 text-left whitespace-normal text-secondary">{{ query }}</span>
                }
              </div>
            </div>
          }

          @if (message().graph_data) {
             <div class="mt-4 pt-3 border-t border-divider">
                <app-graph-visualizer 
                    [data]="message().graph_data"
                    (viewSource)="goToDocument($event)">
                </app-graph-visualizer>
             </div>
          }

          @if (message().sources && message().sources!.length > 0 && (!message().status || message().status === 'completed')) {
            <div class="mt-4 pt-3 border-t border-divider" [class.anime-fade-in]="message().status === 'completed'">
              <p class="text-xs font-medium text-secondary mb-2">
                Sources ({{ message().sources!.length }})
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

      <!-- Actions & Timestamp Row -->
      <div class="flex items-center gap-2 px-1" [class.flex-row-reverse]="message().role === 'user'">
        <!-- Timestamp -->
        <span class="text-[10px] text-secondary opacity-50">
          {{ formatTime(message().created_at) }}
        </span>

        <!-- Actions (Icons) -->
        <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          @if (message().role === 'user' && !isEditing()) {
            <button (click)="toggleEdit()" class="p-1 text-secondary hover:text-primary hover:bg-hover rounded transition-colors" title="Edit">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
            </button>
          }
          
          @if (!isEditing()) {
             <button (click)="copyMessage()" class="p-1 text-secondary hover:text-primary hover:bg-hover rounded transition-colors" title="Copy">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
            </button>
          }
           <!-- Play Audio (Assistant Only) -->
          @if (message().role === 'assistant' && !isEditing()) {
             <button (click)="playAudio()" class="p-1 text-secondary hover:text-primary hover:bg-hover rounded transition-colors" title="Play">
               <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            </button>
          }
        </div>
      </div>
    </div>

    <!-- Source Modal -->
    <app-source-modal
      [isOpen]="isModalOpen()"
      [source]="selectedSource()"
      (close)="closeSourceModal()">
    </app-source-modal>
  `,
  styles: [`
    .message-user { max-width: 85%; margin-left: auto; }
    .message-assistant { max-width: 100%; }
    .message-bubble { border-radius: 16px; padding: 12px 16px; }
    /* User bubble specific override for edit mode */
    .message-user.message-bubble { background-color: var(--color-accent); color: var(--color-accent-content); }
    
    .message-assistant.message-content { color: var(--color-base-content); line-height: 1.7; }
  `]
})
export class MessageBubbleComponent {
  message = input.required<Message>();
  onEdit = output<string>(); // Emits new content

  private modalService = inject(ModalService);
  private voiceService = inject(VoiceService);
  private router = inject(Router);

  // State
  isEditing = signal(false);
  editContent = signal('');

  // Modal state
  isModalOpen = signal(false);
  selectedSource = signal<MessageSource | null>(null);

  toggleEdit() {
    this.editContent.set(this.message().content);
    this.isEditing.set(true);
  }

  cancelEdit() {
    this.isEditing.set(false);
  }

  submitEdit() {
    if (this.editContent().trim() && this.editContent() !== this.message().content) {
      this.onEdit.emit(this.editContent());
    }
    this.isEditing.set(false);
  }

  copyMessage() {
    navigator.clipboard.writeText(this.message().content);
  }

  openImage(index: number, images: string[] | undefined) {
    if (images && images.length > 0) {
      this.modalService.openImageViewer(index, images);
    }
  }

  openSourceModal(source: MessageSource) {
    if (source.file_type === 'youtube' && source.youtube_url) {
      this.modalService.openYoutubeViewer(source.youtube_url, source.start_time);
    } else if (source.document_id && (source.file_type === 'video' || source.file_type === 'audio')) {
      // Open Generic Video/Audio Player
      // We rely on the backend endpoint to serve the file content
      const url = ApiEndpoints.DOCUMENT_CONTENT(source.document_id);
      this.modalService.openVideoPlayer(url, source.start_time);
    } else if (source.document_id && (source.document.toLowerCase().endsWith('.pdf') || source.file_type === 'pdf')) {
      // Create a minimal document object for the viewer
      // We cast to any because we only really need ID and filename for the viewer/title
      const doc: any = {
        id: source.document_id,
        original_filename: source.document,
        file_type: 'pdf'
      };
      this.modalService.openPdfViewer(doc, source.text, source.page_number);
    } else {
      this.selectedSource.set(source);
      this.isModalOpen.set(true);
    }
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

  handleCitation(sourceName: string) {
    if (this.message().sources) {
      // Try exact match first, then partial
      const source = this.message().sources?.find(s =>
        s.document === sourceName ||
        s.document.includes(sourceName) ||
        sourceName.includes(s.document)
      );

      if (source) {
        this.openSourceModal(source);
      }
    }
  }

  goToDocument(docId: string) {
    this.router.navigate(['/library/documents', docId]);
  }

  playAudio() {
    this.voiceService.playMessageAudio(this.message().id);
  }
}
