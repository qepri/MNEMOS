import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Document } from '@core/models';

@Component({
  selector: 'app-document-item',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './document-item.component.html',
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
