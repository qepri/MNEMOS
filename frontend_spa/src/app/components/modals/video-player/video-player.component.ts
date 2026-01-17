import { Component, inject, ViewChild, ElementRef, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ModalService } from '@services/modal.service';

@Component({
    selector: 'app-video-player',
    standalone: true,
    imports: [CommonModule],
    template: `
    @if (isVisible()) {
      <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm transition-opacity anime-fade-in"
          (click)="closeModal()">
          <!-- Modal Container -->
          <div class="bg-black border border-divider rounded-xl w-full max-w-5xl mx-4 flex flex-col shadow-2xl anime-scale-in overflow-hidden"
              (click)="$event.stopPropagation()">

              <!-- Header -->
              <div class="p-3 border-b border-divider flex justify-end items-center bg-panel">
                  <button class="btn-icon text-secondary hover:text-primary transition-colors p-1" (click)="closeModal()">
                      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none"
                          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <path d="M18 6 6 18" />
                          <path d="M6 6 18 18" />
                      </svg>
                  </button>
              </div>

              <!-- Body -->
              <div class="relative w-full aspect-video bg-black flex items-center justify-center">
                  @if (videoUrl()) {
                      <video 
                          #videoPlayer
                          [src]="videoUrl()" 
                          class="w-full h-full object-contain" 
                          controls
                          autoplay
                          (loadedmetadata)="onMetadataLoaded()">
                          Your browser does not support the video tag.
                      </video>
                  } @else {
                      <div class="text-secondary">No video source</div>
                  }
              </div>
          </div>
      </div>
    }
  `
})
export class VideoPlayerComponent {
    private modalService = inject(ModalService);

    @ViewChild('videoPlayer') videoPlayer!: ElementRef<HTMLVideoElement>;

    isVisible = this.modalService.isVideoPlayerOpen;
    videoUrl = this.modalService.videoUrl;
    timestamp = this.modalService.videoTimestamp;

    onMetadataLoaded() {
        const time = this.timestamp();
        if (time !== undefined && time !== null && this.videoPlayer) {
            this.videoPlayer.nativeElement.currentTime = time;
            this.videoPlayer.nativeElement.play().catch(err => console.error("Auto-play blocked", err));
        }
    }

    closeModal() {
        this.modalService.closeVideoPlayer();
    }
}
