import { Component, inject, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ModalService } from '@services/modal.service';

@Component({
  selector: 'app-youtube-viewer',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './youtube-viewer.html',
  styles: [`
    /* Using Tailwind primarily but adding custom fade animations */
  `]
})
export class YoutubeViewer {
  private modalService = inject(ModalService);
  private sanitizer = inject(DomSanitizer);

  isVisible = this.modalService.isYoutubeViewerOpen;
  videoUrl = this.modalService.youtubeVideoUrl;
  timestamp = this.modalService.youtubeTimestamp;

  embedUrl = computed(() => {
    const url = this.videoUrl();
    if (!url) return null;

    const videoId = this.extractVideoId(url);
    if (!videoId) return null;

    let finalUrl = `https://www.youtube.com/embed/${videoId}?autoplay=1`;

    // Add timestamp if available
    const time = this.timestamp();
    if (time !== undefined && time !== null) {
      finalUrl += `&start=${Math.floor(time)}`;
    }

    return this.sanitizer.bypassSecurityTrustResourceUrl(finalUrl);
  });

  closeModal() {
    this.modalService.closeYoutubeViewer();
  }

  private extractVideoId(url: string): string | null {
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
    const match = url.match(regExp);
    return (match && match[2].length === 11) ? match[2] : null;
  }
}
