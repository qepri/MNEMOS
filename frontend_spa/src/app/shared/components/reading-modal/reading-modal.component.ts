import { Component, ElementRef, computed, inject, input, output, signal, viewChild, effect } from '@angular/core';
import { DocumentsService, WindowChunk } from '@services/documents.service';

/**
 * "Read around the passage" modal for formats with no in-app viewer (EPUB,
 * plain text). A document's chunks in order reconstruct its full text, so this
 * opens on the matched chunk and lazily loads neighbours up/down — letting the
 * user read the whole document continuously without a rendering library.
 */
@Component({
  selector: 'app-reading-modal',
  standalone: true,
  template: `
    @if (isOpen()) {
      <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" (click)="close.emit()"></div>

        <div class="relative w-full max-w-2xl bg-panel rounded-2xl shadow-2xl border border-divider overflow-hidden flex flex-col max-h-[85vh]">
          <!-- Header -->
          <div class="flex items-center justify-between p-4 border-b border-divider">
            <h2 class="text-sm font-semibold text-primary truncate pr-4">{{ title() || 'Document' }}</h2>
            <button (click)="close.emit()" class="text-secondary hover:text-primary flex-shrink-0" aria-label="Close">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>

          <!-- Body (scrollable) -->
          <div #body class="p-6 overflow-y-auto flex flex-col gap-4">
            @if (hasPrev()) {
              <button
                class="text-xs text-accent hover:underline self-center disabled:opacity-50"
                [disabled]="loading()"
                (click)="loadEarlier()"
              >{{ loading() ? 'Loading…' : '↑ Load earlier' }}</button>
            }

            @for (c of chunks(); track c.chunk_index) {
              <p
                class="text-sm whitespace-pre-wrap leading-relaxed"
                [class.text-primary]="c.chunk_index === centerIndex()"
                [class.text-secondary]="c.chunk_index !== centerIndex()"
              >{{ c.content }}</p>
            }

            @if (hasNext()) {
              <button
                class="text-xs text-accent hover:underline self-center disabled:opacity-50"
                [disabled]="loading()"
                (click)="loadMore()"
              >{{ loading() ? 'Loading…' : '↓ Load more' }}</button>
            }

            @if (!chunks().length && !loading()) {
              <p class="text-sm text-secondary">No text available.</p>
            }
          </div>
        </div>
      </div>
    }
  `
})
export class ReadingModalComponent {
  private documentsService = inject(DocumentsService);

  isOpen = input.required<boolean>();
  docId = input<string | null>(null);
  title = input<string | null>(null);
  centerIndex = input<number>(0);
  close = output<void>();

  private body = viewChild<ElementRef<HTMLElement>>('body');

  chunks = signal<WindowChunk[]>([]);
  hasPrev = signal(false);
  hasNext = signal(false);
  loading = signal(false);

  // Track the loaded range so load-earlier/more extend from the right edges.
  private loIndex = 0;
  private hiIndex = 0;

  constructor() {
    // Fetch the initial window whenever the modal opens on a new passage.
    effect(() => {
      const open = this.isOpen();
      const id = this.docId();
      const center = this.centerIndex();
      if (!open || !id) return;
      this.loadInitial(id, center);
    });
  }

  private loadInitial(id: string, center: number) {
    this.loading.set(true);
    this.documentsService.getChunkWindow(id, center, 5, 5).subscribe({
      next: (w) => {
        this.chunks.set(w.chunks);
        this.hasPrev.set(w.has_prev);
        this.hasNext.set(w.has_next);
        if (w.chunks.length) {
          this.loIndex = w.chunks[0].chunk_index;
          this.hiIndex = w.chunks[w.chunks.length - 1].chunk_index;
        }
        this.loading.set(false);
      },
      error: () => {
        this.chunks.set([]);
        this.loading.set(false);
      },
    });
  }

  loadEarlier() {
    const id = this.docId();
    if (!id || this.loading()) return;
    this.loading.set(true);
    // Fetch the 10 chunks immediately before the current top edge.
    const center = this.loIndex - 6;
    this.documentsService.getChunkWindow(id, center, 5, 5).subscribe({
      next: (w) => {
        const el = this.body()?.nativeElement;
        const prevHeight = el ? el.scrollHeight : 0;
        // Keep only chunks strictly below our current top edge, then prepend.
        const earlier = w.chunks.filter(c => c.chunk_index < this.loIndex);
        if (earlier.length) {
          this.chunks.update(cur => [...earlier, ...cur]);
          this.loIndex = earlier[0].chunk_index;
        }
        this.hasPrev.set(w.has_prev && earlier.length > 0);
        this.loading.set(false);
        // Preserve reading position: keep the same content under the viewport.
        if (el) {
          requestAnimationFrame(() => {
            el.scrollTop += el.scrollHeight - prevHeight;
          });
        }
      },
      error: () => this.loading.set(false),
    });
  }

  loadMore() {
    const id = this.docId();
    if (!id || this.loading()) return;
    this.loading.set(true);
    const center = this.hiIndex + 6;
    this.documentsService.getChunkWindow(id, center, 5, 5).subscribe({
      next: (w) => {
        const later = w.chunks.filter(c => c.chunk_index > this.hiIndex);
        if (later.length) {
          this.chunks.update(cur => [...cur, ...later]);
          this.hiIndex = later[later.length - 1].chunk_index;
        }
        this.hasNext.set(w.has_next && later.length > 0);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
}
