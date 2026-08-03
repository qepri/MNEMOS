
import { Component, computed, inject, effect, input, signal, untracked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NgxExtendedPdfViewerModule, NgxExtendedPdfViewerService } from 'ngx-extended-pdf-viewer';
import { ModalService } from '@services/modal.service';
import { ApiEndpoints } from '@core/constants/api-endpoints';

const MAX_SEARCH_SNIPPET_CHARS = 100;

/**
 * Callers pass a source's raw text: the whole chunk (~932 chars average) for
 * RAG citations, or content[:200] + '...' for graph/wiki sources. Neither
 * matches in pdf.js - extracted PDF text carries its own line breaks and
 * hyphenation, and the literal '...' is not in the document at all - and
 * scanning for a string that long is slow. Reduce it to a distinctive
 * opening snippet cut on a word boundary.
 */
export function toSearchSnippet(raw: string): string {
    const cleaned = raw
        .replace(/[.…]+\s*$/, '')
        .replace(/\s+/g, ' ')
        .trim();

    if (cleaned.length <= MAX_SEARCH_SNIPPET_CHARS) return cleaned;

    const cut = cleaned.slice(0, MAX_SEARCH_SNIPPET_CHARS);
    const lastSpace = cut.lastIndexOf(' ');
    return (lastSpace > 0 ? cut.slice(0, lastSpace) : cut).trim();
}

@Component({
    selector: 'app-pdf-viewer',
    standalone: true,
    imports: [CommonModule, NgxExtendedPdfViewerModule],
    templateUrl: './pdf-viewer.component.html',
    styles: [`
    :host { display: block; }
    .pdf-container { height: calc(90vh - 60px); } /* Adjust based on header height */

    /* Hides the kept-alive viewer without display:none, which would collapse
       it to zero width and make pdf.js mis-scale the page on reopen. */
    .pdf-viewer-hidden {
      opacity: 0;
      pointer-events: none;
    }
  `]
})
export class PdfViewerComponent {
    modalService = inject(ModalService);
    pdfService = inject(NgxExtendedPdfViewerService);

    // Theme input
    theme = input<'dark' | 'light'>('dark');

    // Computed
    isVisible = this.modalService.isPdfViewerOpen;
    currentDoc = this.modalService.pdfDocument;

    // Search & Page
    page = computed(() => this.modalService.pdfPage() || 1);
    searchTerm = this.modalService.pdfSearchTerm;

    /**
     * The viewer is kept mounted once opened, so pdf.js is not torn down and
     * re-bootstrapped (worker spawn + document parse + render) on every open.
     * closePdfViewer() clears pdfDocument, so the last src is retained here
     * rather than being allowed to go undefined and destroy the viewer.
     */
    private readonly retainedSrc = signal<string | undefined>(undefined);
    src = this.retainedSrc.asReadonly();
    hasOpened = computed(() => this.retainedSrc() !== undefined);

    // Whether the currently loaded document has rendered its text layer.
    private textLayerReady = false;
    // textLayerRendered fires once per page; the search is one-shot per open.
    private searchDone = false;

    constructor() {
        effect(() => {
            const doc = this.currentDoc();
            if (!doc) return; // Closing must not drop the src.

            const next = ApiEndpoints.DOCUMENT_CONTENT(doc.id);
            untracked(() => {
                if (next === this.retainedSrc()) return;
                // A different document has to render before it can be searched.
                this.textLayerReady = false;
                this.retainedSrc.set(next);
            });
        });

        effect(() => {
            if (!this.isVisible()) return;
            untracked(() => this.onOpened());
        });
    }

    closeModal() {
        this.modalService.closePdfViewer();
    }

    /**
     * Reopening the same document renders nothing new, so textLayerRendered
     * never fires again - search straight away in that case, otherwise wait
     * for the text layer.
     */
    onOpened() {
        this.searchDone = false;
        if (this.textLayerReady) this.runSearch();
    }

    onTextLayerRendered() {
        this.textLayerReady = true;
        this.runSearch();
    }

    private runSearch() {
        // Driven by the text layer actually being ready rather than a fixed
        // delay: highlighting previously waited a blanket 500ms after
        // pdfLoaded, which is both visibly slow on fast machines and too
        // early on slow ones (find() against a text layer that isn't there
        // yet silently highlights nothing).
        const term = this.searchTerm();
        if (!term || this.searchDone) return;

        const snippet = toSearchSnippet(term);
        if (!snippet) return;

        this.searchDone = true;
        this.pdfService.find(snippet, {
            // highlightAll would make pdf.js extract and scan the text of
            // every page to collect all matches - on a 224-page book that is
            // the visible lag before the highlight appears. A ~100 char
            // citation snippet realistically occurs once, and the search
            // starts from the page we already navigated to, so stopping at
            // the first match costs nothing and skips the full-document scan.
            highlightAll: false,
            matchCase: false,
            wholeWords: false,
        });
    }

    onPdfError(error: any) {
        console.error('PDF Loading Failed', error);
    }
}
