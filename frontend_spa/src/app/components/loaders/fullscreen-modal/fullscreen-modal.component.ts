import { Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
    selector: 'app-fullscreen-modal',
    standalone: true,
    imports: [CommonModule],
    template: `
    <div class="fixed inset-0 z-[9999] bg-base flex flex-col items-center justify-center transition-opacity duration-500 ease-in-out"
        [class.opacity-0]="!isLoading()" [class.pointer-events-none]="!isLoading()">
        <div class="flex flex-col items-center gap-6">
            <div class="relative w-20 h-20">
                <div
                    class="absolute inset-0 border-4 border-divider rounded-full">
                </div>
                <div
                    class="absolute inset-0 border-4 border-accent border-t-transparent rounded-full animate-spin">
                </div>
            </div>
            <div class="text-2xl font-bold text-primary tracking-widest animate-pulse">MNEMOS</div>
        </div>
    </div>
  `
})
export class FullscreenModalComponent {
    isLoading = input.required<boolean>();
}
