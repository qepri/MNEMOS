import { Component, signal, inject } from '@angular/core';
import { DocumentsService, SearchResult } from '@services/documents.service';

/**
 * LLM-free search page. Sends a query to /api/documents/search and lists the
 * matching passages. Unlike Chat, this needs no language model — it's the
 * retrieval entry point when a provider is dormant.
 */
@Component({
  selector: 'app-search',
  standalone: true,
  template: `
<div class="max-w-3xl mx-auto w-full px-4 py-6 flex flex-col gap-4">

  <header>
    <h1 class="text-lg font-semibold text-primary">Search</h1>
    <p class="text-xs text-secondary">Find passages across your library. No language model required.</p>
  </header>

  <form class="flex gap-2" (submit)="onSubmit($event)">
    <input
      type="text"
      class="flex-1 px-3 py-2 text-sm rounded-lg bg-input border border-default text-primary focus:outline-none focus:ring-1 focus:ring-accent"
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
    <p class="text-xs text-secondary">Searching…</p>
  } @else if (searched()) {
    <p class="text-xs text-secondary">
      {{ results().length }} passage{{ results().length !== 1 ? 's' : '' }} for "{{ lastQuery() }}"
    </p>
  }

  <section class="flex flex-col gap-3">
    @for (r of results(); track r.id) {
      <article class="p-3 rounded-lg bg-card border border-default">
        <div class="flex items-center justify-between mb-1">
          <span class="text-xs font-medium text-primary truncate">
            {{ r.document_title || 'Untitled' }}
          </span>
          @if (r.page_number != null) {
            <span class="text-[11px] text-secondary flex-shrink-0 ml-2">p.{{ r.page_number }}</span>
          } @else if (r.start_time != null) {
            <span class="text-[11px] text-secondary flex-shrink-0 ml-2">{{ formatTime(r.start_time) }}</span>
          }
        </div>
        <p class="text-sm text-secondary whitespace-pre-wrap">{{ r.content }}</p>
      </article>
    }
    @if (searched() && !loading() && results().length === 0) {
      <p class="text-sm text-secondary">No matching passages found.</p>
    }
  </section>
</div>
  `
})
export class SearchComponent {
  private documentsService = inject(DocumentsService);

  query = signal('');
  lastQuery = signal('');
  results = signal<SearchResult[]>([]);
  loading = signal(false);
  searched = signal(false);

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

  formatTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }
}
