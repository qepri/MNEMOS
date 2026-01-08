
import { Component, computed, inject, effect, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NgxExtendedPdfViewerModule, NgxExtendedPdfViewerService } from 'ngx-extended-pdf-viewer';
import { ModalService } from '@services/modal.service';
import { ApiEndpoints } from '@core/constants/api-endpoints';

@Component({
    selector: 'app-pdf-viewer',
    standalone: true,
    imports: [CommonModule, NgxExtendedPdfViewerModule],
    templateUrl: './pdf-viewer.component.html',
    styles: [`
    :host { display: block; }
    .pdf-container { height: calc(90vh - 60px); } /* Adjust based on header height */
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

    pdfSrc = computed(() => {
        const doc = this.currentDoc();
        if (!doc) return undefined;
        const src = ApiEndpoints.DOCUMENT_CONTENT(doc.id);
        console.log('PDF Viewer Src:', src);
        return src;
    });

    closeModal() {
        this.modalService.closePdfViewer();
    }

    onPdfLoaded(event: any) {
        console.log('PDF Loaded successfully', event);
        const term = this.searchTerm();
        if (term) {
            // Delay slightly to ensure rendering
            setTimeout(() => {
                this.pdfService.find(term, {
                    highlightAll: true,
                    matchCase: false,
                    wholeWords: false,
                    // If we have a page number, we rely on [page] binding to go there first
                    // But find() might jump around. 
                });
            }, 500);
        }
    }

    onPdfError(error: any) {
        console.error('PDF Loading Failed', error);
    }
}
