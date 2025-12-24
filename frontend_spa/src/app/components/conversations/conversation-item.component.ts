import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Conversation } from '@core/models';

@Component({
  selector: 'app-conversation-item',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div
      (click)="select.emit(conversation().id)"
      class="flex items-center gap-3 p-3 hover:bg-base-200 rounded-lg transition-colors group cursor-pointer"
      [class.bg-primary/10]="isActive()"
    >
      <div class="flex-1 min-w-0">
        <div class="font-medium text-sm truncate">
          {{ conversation().title }}
        </div>
        <div class="text-xs text-base-content/60">
          {{ formatDate(conversation().updated_at) }}
        </div>
      </div>

      <button
        (click)="handleDelete($event)"
        class="btn btn-ghost btn-sm btn-circle opacity-0 group-hover:opacity-100 transition-opacity"
        title="Eliminar conversación"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  `
})
export class ConversationItemComponent {
  conversation = input.required<Conversation>();
  isActive = input<boolean>(false);

  select = output<string>();
  delete = output<string>();

  handleDelete(event: Event) {
    event.stopPropagation();
    this.delete.emit(this.conversation().id);
  }

  formatDate(timestamp: string): string {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString();
  }
}
