import { Component, input, output, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
    selector: 'app-image-modal',
    standalone: true,
    imports: [CommonModule],
    template: `
    @if (isOpen()) {
      <div class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm anime-fade-in" (click)="close.emit()">
        
        <!-- Close Button (Top Right) -->
        <button 
          class="absolute top-4 right-4 p-2 text-white/70 hover:text-white bg-black/20 hover:bg-black/40 rounded-full transition-colors z-[102]"
          (click)="close.emit()">
          <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
          </svg>
        </button>

        <!-- Navigation Buttons -->
        @if (showNav()) {
            <!-- Prev -->
            <button 
                class="absolute left-4 top-1/2 -translate-y-1/2 p-3 text-white/70 hover:text-white bg-black/20 hover:bg-black/40 rounded-full transition-colors z-[101]"
                (click)="$event.stopPropagation(); prev.emit()">
                <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
                </svg>
            </button>

            <!-- Next -->
            <button 
                class="absolute right-4 top-1/2 -translate-y-1/2 p-3 text-white/70 hover:text-white bg-black/20 hover:bg-black/40 rounded-full transition-colors z-[101]"
                (click)="$event.stopPropagation(); next.emit()">
                <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                </svg>
            </button>
        }

        <!-- Image Container -->
        <div class="relative max-w-full max-h-full overflow-auto flex items-center justify-center" (click)="$event.stopPropagation()">
            <!-- Use key based on url to trigger animation restart if needed, or simply let angular handle src change -->
            <img [src]="imageUrl()" 
                 alt="Full size preview" 
                 class="max-w-[95vw] max-h-[95vh] object-contain rounded-lg shadow-2xl animate-zoom-in select-none"
                 (contextmenu)="$event.preventDefault()">
        </div>
      </div>
    }
  `,
    styles: [`
    .anime-fade-in {
      animation: fadeIn 0.2s ease-out forwards;
    }
    .animate-zoom-in {
        animation: zoomIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }

    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
    @keyframes zoomIn {
      from { transform: scale(0.9); opacity: 0; }
      to { transform: scale(1); opacity: 1; }
    }
  `]
})
export class ImageModalComponent {
    isOpen = input.required<boolean>();
    imageUrl = input.required<string | null>();
    showNav = input<boolean>(false);

    close = output<void>();
    next = output<void>();
    prev = output<void>();

    @HostListener('document:keydown', ['$event'])
    handleKeyboardEvent(event: KeyboardEvent) {
        if (!this.isOpen()) return;

        if (event.key === 'Escape') {
            this.close.emit();
        } else if (this.showNav()) {
            if (event.key === 'ArrowRight') {
                this.next.emit();
            } else if (event.key === 'ArrowLeft') {
                this.prev.emit();
            }
        }
    }
}
