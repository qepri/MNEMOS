import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
    selector: 'app-progress-bar',
    standalone: true,
    imports: [CommonModule],
    template: `
    <div class="w-full">
      <div class="flex justify-between items-center mb-1">
        <span class="text-sm font-medium text-base-content">{{ label }}</span>
        <span class="text-sm font-medium text-base-content">{{ progress | number:'1.0-0' }}%</span>
      </div>
      <div class="w-full bg-base-300 rounded-full h-2.5 dark:bg-base-300">
        <div class="bg-accent h-2.5 rounded-full transition-all duration-300 ease-out"
             [style.width.%]="progress"
             [class.bg-success]="status === 'completed'"
             [class.bg-error]="status === 'error'">
        </div>
      </div>
      @if (message) {
        <p class="text-xs text-secondary mt-1 truncate">{{ message }}</p>
      }
    </div>
  `
})
export class ProgressBarComponent {
    @Input() progress: number = 0;
    @Input() label: string = '';
    @Input() message: string = '';
    @Input() status: 'pending' | 'downloading' | 'completed' | 'error' = 'downloading';
}
