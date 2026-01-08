import { Injectable, signal } from '@angular/core';
import { Document } from '@core/models';

@Injectable({
    providedIn: 'root'
})
export class ModalService {
    isUploadOpen = signal(false);


    // Upload Modal
    openUpload() {
        this.isUploadOpen.set(true);
    }

    closeUpload() {
        this.isUploadOpen.set(false);
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

    // YouTube Viewer Modal
    isYoutubeViewerOpen = signal(false);
    youtubeVideoUrl = signal<string | null>(null);
    youtubeTimestamp = signal<number | undefined>(undefined);

    openYoutubeViewer(url: string, timestamp?: number) {
        this.youtubeVideoUrl.set(url);
        this.youtubeTimestamp.set(timestamp);
        this.isYoutubeViewerOpen.set(true);
    }

    closeYoutubeViewer() {
        this.isYoutubeViewerOpen.set(false);
        this.youtubeVideoUrl.set(null);
        this.youtubeTimestamp.set(undefined);
    }

    // Video Player Modal (Local/Uploaded Files)
    isVideoPlayerOpen = signal(false);
    videoUrl = signal<string | null>(null);
    videoTimestamp = signal<number | undefined>(undefined);

    openVideoPlayer(url: string, timestamp?: number) {
        this.videoUrl.set(url);
        this.videoTimestamp.set(timestamp);
        this.isVideoPlayerOpen.set(true);
    }

    closeVideoPlayer() {
        this.isVideoPlayerOpen.set(false);
        this.videoUrl.set(null);
        this.videoTimestamp.set(undefined);
    }
    // Image Viewer Modal
    isImageViewerOpen = signal(false);
    images = signal<string[]>([]);
    currentImageIndex = signal<number>(0);

    // Computed or Helper to get current
    get currentImageUrl(): string | null {
        const imgs = this.images();
        const idx = this.currentImageIndex();
        if (imgs.length > 0 && idx >= 0 && idx < imgs.length) {
            return imgs[idx];
        }
        return null;
    }

    openImageViewer(index: number, images: string[]) {
        this.images.set(images);
        this.currentImageIndex.set(index);
        this.isImageViewerOpen.set(true);
    }

    closeImageViewer() {
        this.isImageViewerOpen.set(false);
        this.images.set([]);
        this.currentImageIndex.set(0);
    }

    nextImage() {
        const len = this.images().length;
        if (len <= 1) return;
        this.currentImageIndex.update(i => (i + 1) % len);
    }

    prevImage() {
        const len = this.images().length;
        if (len <= 1) return;
        this.currentImageIndex.update(i => (i - 1 + len) % len);
    }
}
