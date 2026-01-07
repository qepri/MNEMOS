import { Injectable, signal } from '@angular/core';
import { Document } from '@core/models';

@Injectable({
    providedIn: 'root'
})
export class ModalService {
    isUploadOpen = signal(false);
    isModelSelectionOpen = signal(false);

    // Upload Modal
    openUpload() {
        this.isUploadOpen.set(true);
    }

    closeUpload() {
        this.isUploadOpen.set(false);
    }

    // Model Selection Modal
    openModelSelection() {
        this.isModelSelectionOpen.set(true);
    }

    closeModelSelection() {
        this.isModelSelectionOpen.set(false);
    }

    // PDF Viewer Modal
    isPdfViewerOpen = signal(false);
    pdfDocument = signal<Document | null>(null);
    pdfSearchTerm = signal<string | null>(null);
    pdfPage = signal<number | undefined>(undefined);

    openPdfViewer(doc: Document, searchTerm?: string, page?: number) {
        this.pdfDocument.set(doc);
        this.pdfSearchTerm.set(searchTerm || null);
        this.pdfPage.set(page);
        this.isPdfViewerOpen.set(true);
    }

    closePdfViewer() {
        this.isPdfViewerOpen.set(false);
        this.pdfDocument.set(null);
        this.pdfSearchTerm.set(null);
        this.pdfPage.set(undefined);
    }
}
