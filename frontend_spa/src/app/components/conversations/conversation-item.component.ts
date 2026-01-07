import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Conversation } from '@core/models';

@Component({
  selector: 'app-conversation-item',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './conversation-item.component.html',
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
