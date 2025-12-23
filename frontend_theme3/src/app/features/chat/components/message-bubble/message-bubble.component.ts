import { Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Message } from '@core/models';

@Component({
    selector: 'app-message-bubble',
    standalone: true,
    imports: [CommonModule],
    templateUrl: './message-bubble.component.html',
    styleUrl: './message-bubble.component.css'
})
export class MessageBubbleComponent {
    message = input.required<Message>();
}
