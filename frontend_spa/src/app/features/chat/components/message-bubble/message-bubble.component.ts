import { Component, input, computed, inject, ViewEncapsulation } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { Message } from '@core/models';
import { marked } from 'marked';

@Component({
    selector: 'app-message-bubble',
    standalone: true,
    imports: [CommonModule],
    templateUrl: './message-bubble.component.html',
    styleUrl: './message-bubble.component.css',
    encapsulation: ViewEncapsulation.None // Disable encapsulation to let global styles apply easily
})
export class MessageBubbleComponent {
    message = input.required<Message>();
    private sanitizer = inject(DomSanitizer);

    // Parse and sanitize markdown content
    parsedContent = computed(() => {
        if (this.message().role === 'user') {
            return this.message().content;
        }

        // Parse markdown (marked returns string | Promise, handle sync for now as default is sync)
        const rawHtml = marked.parse(this.message().content, { async: false }) as string;
        return this.sanitizer.bypassSecurityTrustHtml(rawHtml);
    });
}
