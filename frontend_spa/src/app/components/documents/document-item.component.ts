import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Document } from '@core/models';

@Component({
  selector: 'app-document-item',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="flex items-center gap-3 p-3 hover:bg-hover rounded-lg transition-colors group">
      <input
        type="checkbox"
        [checked]="document().selected || false"
        (change)="toggle.emit(document().id)"
        class="checkbox checkbox-sm checkbox-primary"
        [disabled]="document().status !== 'completed'"
      />

      <div class="flex-1 min-w-0">
        <div class="font-medium text-sm truncate">
          {{ document().original_filename }}
        </div>
        <div class="flex items-center gap-2 text-xs text-base-content/60">
          <span class="badge badge-xs" [class]="getStatusClass()">
            {{ getStatusText() }}
          </span>
          <span class="uppercase">{{ document().file_type }}</span>
        </div>

        @if (document().error_message) {
          <div class="text-xs text-error mt-1">
            {{ document().error_message }}
          </div>
        }
      </div>

      <button
        (click)="delete.emit(document().id)"
        class="btn btn-ghost btn-sm btn-circle opacity-0 group-hover:opacity-100 transition-opacity"
        title="Eliminar"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  `,
  styles: [`
    :host { display: block; }
    .group { transition: all 0.2s; }
    .group:hover { background-color: var(--color-hover); }
    input:checked ~ div { opacity: 1; }
    input:not(:checked) ~ div { opacity: 0.7; }
  `]
})
export class DocumentItemComponent {
  document = input.required<Document>();

  toggle = output<string>();
  delete = output<string>();

  getStatusClass(): string {
    const status = this.document().status;
    switch (status) {
      case 'completed':
        return 'badge-success';
      case 'processing':
      case 'pending':
        return 'badge-warning';
      case 'failed':
        return 'badge-error';
      default:
        return 'badge-ghost';
    }
  }

  getStatusText(): string {
    const status = this.document().status;
    switch (status) {
      case 'completed':
        return 'Ready';
      case 'processing':
        return 'Processing...';
      case 'pending':
        return 'Pending...';
      case 'failed':
        return 'Failed';
      default:
        return status;
    }
  }
}
