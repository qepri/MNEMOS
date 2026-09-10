import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { of, throwError } from 'rxjs';
import { describe, it, expect, beforeEach, vi } from 'vitest';

import { SearchComponent } from './search.component';
import { DocumentsService, SearchResponse, SearchResult } from '@services/documents.service';
import { ModalService } from '@services/modal.service';

/**
 * Covers the three mutually-exclusive search outcomes (FR-001..FR-003, SC-002):
 * results, a genuine empty result, and a request error. The regression this
 * guards: a failed request must NOT render the "No matching passages found."
 * empty state — otherwise a broken backend is indistinguishable from an empty
 * library.
 */

function makeResult(overrides: Partial<SearchResult> = {}): SearchResult {
  return {
    id: 'chunk-1',
    content: 'A matching passage.',
    chunk_index: 3,
    page_number: null,
    start_time: null,
    end_time: null,
    document_id: 'doc-1',
    document_title: 'My Book.epub',
    file_type: 'epub',
    ...overrides,
  };
}

describe('SearchComponent', () => {
  let fixture: ComponentFixture<SearchComponent>;
  const searchChunks = vi.fn();
  const modalStub = {
    openPdfViewer: vi.fn(),
    openVideoPlayer: vi.fn(),
  };

  function bodyText(): string {
    return (fixture.nativeElement.textContent as string) ?? '';
  }

  async function setup() {
    await TestBed.configureTestingModule({
      imports: [SearchComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: DocumentsService, useValue: { searchChunks } },
        { provide: ModalService, useValue: modalStub },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(SearchComponent);
    fixture.detectChanges();
  }

  function submitQuery(q = 'quantum') {
    const cmp = fixture.componentInstance;
    cmp.query.set(q);
    cmp.onSubmit(new Event('submit'));
    fixture.detectChanges();
  }

  beforeEach(async () => {
    searchChunks.mockReset();
    modalStub.openPdfViewer.mockReset();
    modalStub.openVideoPlayer.mockReset();
    await setup();
  });

  it('renders the matching passages when the search returns results', () => {
    const res: SearchResponse = { query: 'quantum', count: 1, results: [makeResult()] };
    searchChunks.mockReturnValue(of(res));

    submitQuery();

    expect(fixture.componentInstance.results().length).toBe(1);
    expect(fixture.componentInstance.error()).toBeNull();
    expect(bodyText()).toContain('A matching passage.');
    expect(bodyText()).not.toContain('No matching passages found.');
    expect(bodyText()).not.toContain('Search failed');
  });

  it('shows the empty state when the search genuinely returns zero results', () => {
    const res: SearchResponse = { query: 'nothing', count: 0, results: [] };
    searchChunks.mockReturnValue(of(res));

    submitQuery('nothing');

    expect(fixture.componentInstance.results().length).toBe(0);
    expect(fixture.componentInstance.error()).toBeNull();
    expect(bodyText()).toContain('No matching passages found.');
    expect(bodyText()).not.toContain('Search failed');
  });

  it('shows a distinct error state when the request fails (not the empty state)', () => {
    searchChunks.mockReturnValue(throwError(() => new Error('network down')));

    submitQuery();

    expect(fixture.componentInstance.error()).toBeTruthy();
    expect(bodyText()).toContain('Search failed — please try again.');
    // The critical regression guard: a failure must not read as an empty library.
    expect(bodyText()).not.toContain('No matching passages found.');
  });

  it('clears a prior error when a subsequent search succeeds', () => {
    searchChunks.mockReturnValueOnce(throwError(() => new Error('network down')));
    submitQuery();
    expect(fixture.componentInstance.error()).toBeTruthy();

    searchChunks.mockReturnValueOnce(of({ query: 'quantum', count: 1, results: [makeResult()] }));
    submitQuery();

    expect(fixture.componentInstance.error()).toBeNull();
    expect(bodyText()).toContain('A matching passage.');
    expect(bodyText()).not.toContain('Search failed');
  });
});
