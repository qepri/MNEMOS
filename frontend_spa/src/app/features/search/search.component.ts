import { Component, signal, inject } from '@angular/core';
import { DocumentsService, SearchResult } from '@services/documents.service';
import { ModalService } from '@services/modal.service';
import { ApiEndpoints } from '@core/constants/api-endpoints';
import { MessageSource } from '@core/models';
import { SourceModalComponent } from '@shared/components/source-modal';

/**
 * LLM-free search page. Sends a query to /api/documents/search and lists the
 * matching passages. Unlike Chat, this needs no language model — it's the
 * retrieval entry point when a provider is dormant.
 */
@Component({
  selector: 'app-search',
  standalone: true,
  imports: [SourceModalComponent],
  template: `
<!-- h-full + inner overflow: the router outlet gives us a fixed-height,
     overflow-hidden box, so the page itself must own its scroll region. -->
<div class="h-full flex flex-col max-w-3xl mx-auto w-full px-4">

  <header class="pt-6 pb-4 flex-shrink-0">
    <h1 class="text-lg font-semibold text-primary">Search</h1>
    <p class="text-xs text-secondary">Find passages across your library. No language model required.</p>

    <form class="flex gap-2 mt-4" (submit)="onSubmit($event)">
      <input
        type="text"
        class="flex-1 px-3 py-2 text-sm rounded-lg bg-input border border-divider text-primary focus:outline-none focus:ring-1 focus:ring-accent"
        placeholder="Search your documents…"
        [value]="query()"
        (input)="query.set($any($event.target).value)"
        autocomplete="off"
        autofocus
      >
      <button
        type="submit"
        class="px-4 py-2 text-sm rounded-lg bg-accent text-white disabled:opacity-50"
        [disabled]="loading() || !query().trim()"
      >Search</button>
    </form>

    @if (loading()) {
      <p class="text-xs text-secondary mt-3">Searching…</p>
    } @else if (searched()) {
      <p class="text-xs text-secondary mt-3">
        {{ results().length }} passage{{ results().length !== 1 ? 's' : '' }} for "{{ lastQuery() }}"
      </p>
    }
  </header>

  <!-- Scrollable results -->
  <section class="flex-1 overflow-y-auto flex flex-col gap-3 pb-6">
    @for (r of results(); track r.id) {
      <article class="p-3 rounded-lg bg-panel border border-divider">
        <div class="flex items-center justify-between mb-1 gap-2">
          <span class="text-xs font-medium text-primary truncate">
            {{ r.document_title || 'Untitled' }}
          </span>
          <div class="flex items-center gap-2 flex-shrink-0">
            @if (r.page_number != null) {
              <span class="text-[11px] text-secondary">p.{{ r.page_number }}</span>
            } @else if (r.start_time != null) {
              <span class="text-[11px] text-secondary">{{ formatTime(r.start_time) }}</span>
            }
            <button
              class="text-[11px] text-accent hover:underline"
              (click)="openResult(r)"
            >{{ viewLabel(r) }}</button>
          </div>
        </div>
        <p class="text-sm text-secondary whitespace-pre-wrap">{{ r.content }}</p>
      </article>
    }
    @if (searched() && !loading() && results().length === 0) {
      <p class="text-sm text-secondary">No matching passages found.</p>
    }
  </section>
</div>

<!-- Text-detail fallback for formats with no in-app viewer (EPUB, plain text).
     The PDF/video/youtube viewers are mounted globally in the layout. -->
<app-source-modal
  [isOpen]="isModalOpen()"
  [source]="selectedSource()"
  (close)="closeModal()"
></app-source-modal>
  `
})
export class SearchComponent {
  private documentsService = inject(DocumentsService);
  private modalService = inject(ModalService);

  query = signal('');
  lastQuery = signal('');
  results = signal<SearchResult[]>([]);
  loading = signal(false);
  searched = signal(false);

  // Text-detail modal (fallback for EPUB / plain text)
  isModalOpen = signal(false);
  selectedSource = signal<MessageSource | null>(null);

  onSubmit(event: Event) {
    event.preventDefault();
    const q = this.query().trim();
    if (!q || this.loading()) return;

    this.loading.set(true);
    this.lastQuery.set(q);
    this.documentsService.searchChunks(q, undefined, 20).subscribe({
      next: (res) => {
        this.results.set(res.results);
        this.searched.set(true);
        this.loading.set(false);
      },
      error: () => {
        this.results.set([]);
        this.searched.set(true);
        this.loading.set(false);
      },
    });
  }

  private isPdf(r: SearchResult): boolean {
    return r.file_type === 'pdf' || (r.document_title || '').toLowerCase().endsWith('.pdf');
  }

  viewLabel(r: SearchResult): string {
    if (this.isPdf(r)) return 'View in PDF';
    if (r.file_type === 'video' || r.file_type === 'audio') return 'Play';
    return 'View passage';
  }

  /**
   * Route each result to the same viewer chat uses for that file type. Only
   * PDF/video/audio/youtube have real viewers; EPUB and plain text have none,
   * so they fall back to the text-detail modal (as chat citations do too).
   */
  openResult(r: SearchResult) {
    if (this.isPdf(r)) {
      const doc: any = {
        id: r.document_id,
        original_filename: r.document_title || 'Document',
        file_type: 'pdf',
      };
      // Pass the chunk text as the search term so pdf.js highlights it.
      this.modalService.openPdfViewer(doc, r.content, r.page_number ?? undefined);
      return;
    }

    if ((r.file_type === 'video' || r.file_type === 'audio') && r.document_id) {
      const url = ApiEndpoints.DOCUMENT_CONTENT(r.document_id);
      this.modalService.openVideoPlayer(url, r.start_time ?? undefined);
      return;
    }

    // EPUB / text / anything else without a viewer → readable text modal.
    this.selectedSource.set({
      document: r.document_title || 'Untitled',
      document_id: r.document_id,
      page_number: r.page_number ?? undefined,
      start_time: r.start_time ?? undefined,
      end_time: r.end_time ?? undefined,
      text: r.content,
      file_type: r.file_type ?? undefined,
      score: 0,
      location: r.page_number != null ? `p.${r.page_number}` : undefined,
    });
    this.isModalOpen.set(true);
  }

  closeModal() {
    this.isModalOpen.set(false);
    this.selectedSource.set(null);
  }

  formatTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }
}
