import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MessageSource } from '@core/models';

@Component({
  selector: 'app-source-modal',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (isOpen()) {
      <div class="fixed inset-0 z-50 flex items-center justify-center p-4 modal">
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black bg-opacity-60 backdrop-blur-sm" (click)="close.emit()"></div>

        <!-- Modal Content -->
        <div class="relative w-full max-w-2xl bg-panel rounded-2xl shadow-xl border border-divider overflow-hidden anime-fade-in">
          <!-- Header -->
          <div class="flex items-center justify-between p-6 border-b border-divider">
            <h2 class="text-xl font-semibold text-primary">Source Details</h2>
            <button
              (click)="close.emit()"
              class="btn-icon"
              aria-label="Close modal">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>

          <!-- Body -->
          <div class="p-6 max-h-96 overflow-y-auto">
            @if (source()) {
              <div class="space-y-4">
                <!-- Document Name -->
                <div>
                  <label class="text-xs font-medium text-secondary uppercase tracking-wide">Document</label>
                  <p class="mt-1 text-primary font-semibold">{{ source()!.document }}</p>
                </div>

                <!-- Content -->
                <div>
                  <label class="text-xs font-medium text-secondary uppercase tracking-wide">Content</label>
                  <div class="mt-2 p-4 bg-input rounded-lg border border-divider">
                    <p class="text-primary whitespace-pre-wrap leading-relaxed">{{ source()!.chunk }}</p>
                  </div>
                </div>

                <!-- Score -->
                <div>
                  <label class="text-xs font-medium text-secondary uppercase tracking-wide">Relevance Score</label>
                  <div class="mt-1 flex items-center gap-2">
                    <div class="flex-1 bg-input rounded-full h-2 overflow-hidden">
                      <div
                        class="h-full bg-accent transition-all duration-300"
                        [style.width.%]="(source()!.score || 0) * 100">
                      </div>
                    </div>
                    <span class="text-sm font-medium text-primary">{{ formatScore(source()!.score) }}</span>
                  </div>
                </div>
              </div>
            }
          </div>

          <!-- Footer -->
          <div class="flex justify-end p-6 border-t border-divider">
            <button
              (click)="close.emit()"
              class="btn-primary">
              Close
            </button>
          </div>
        </div>
      </div>
    }
  `,
  styles: [`
    .anime-fade-in {
      animation: fadeIn 0.2s ease-out forwards;
    }

    @keyframes fadeIn {
      from {
        opacity: 0;
        transform: scale(0.95);
      }
      to {
        opacity: 1;
        transform: scale(1);
      }
    }
  `]
})
export class SourceModalComponent {
  isOpen = input.required<boolean>();
  source = input<MessageSource | null>(null);
  close = output<void>();

  formatScore(score: number | undefined): string {
    if (score === undefined || score === null || isNaN(score)) {
      return 'N/A';
    }
    return `${(score * 100).toFixed(1)}%`;
  }
}
