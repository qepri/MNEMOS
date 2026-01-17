import { Component, input, effect, signal, inject, ViewEncapsulation, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { marked } from 'marked';

@Component({
    selector: 'app-markdown-display',
    standalone: true,
    imports: [CommonModule],
    template: `
    <div class="markdown-content" [innerHTML]="sanitizedContent()" (click)="handleContentClick($event)"></div>
  `,
    styles: [`
    .markdown-content {
      font-size: 0.95rem;
      line-height: 1.6;
      color: inherit;
    }

    /* Headers */
    .markdown-content h1, 
    .markdown-content h2, 
    .markdown-content h3, 
    .markdown-content h4 {
      font-weight: 600;
      margin-top: 1.5em;
      margin-bottom: 0.75em;
      color: inherit;
    }
    .markdown-content h1 { font-size: 1.5em; }
    .markdown-content h2 { font-size: 1.25em; }
    .markdown-content h3 { font-size: 1.1em; }

    /* Paragraphs */
    .markdown-content p {
      margin-bottom: 1em;
    }
    .markdown-content p:last-child {
      margin-bottom: 0;
    }

    /* Links */
    .markdown-content a {
      color: var(--color-accent);
      text-decoration: underline;
    }

    /* Lists */
    .markdown-content ul, 
    .markdown-content ol {
      padding-left: 1.5em;
      margin-bottom: 1em;
    }
    .markdown-content ul { list-style-type: disc; }
    .markdown-content ol { list-style-type: decimal; }

    /* Code Blocks */
    .markdown-content pre {
      background-color: rgba(0, 0, 0, 0.2);
      border: 1px solid var(--color-divider);
      border-radius: 0.5rem;
      padding: 1em;
      overflow-x: auto;
      margin-bottom: 1em;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    .markdown-content code {
      background-color: rgba(255, 255, 255, 0.1);
      padding: 0.2em 0.4em;
      border-radius: 0.25rem;
      font-size: 0.85em;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    .markdown-content pre code {
      background-color: transparent;
      padding: 0;
      font-size: 0.9em;
      color: inherit;
    }

    /* Tables */
    .markdown-content table {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 1em;
      display: block;
      overflow-x: auto;
    }
    .markdown-content th,
    .markdown-content td {
      padding: 0.75em 1em;
      border: 1px solid var(--color-divider);
      text-align: left;
    }
    .markdown-content th {
      background-color: rgba(0, 0, 0, 0.1);
      font-weight: 600;
    }
    .markdown-content tr:nth-child(even) {
      background-color: rgba(255, 255, 255, 0.02);
    }

    /* Blockquotes */
    .markdown-content blockquote {
      border-left: 4px solid var(--color-accent);
      padding-left: 1em;
      margin-left: 0;
      margin-bottom: 1em;
      font-style: italic;
      color: rgba(255, 255, 255, 0.7);
    }

    /* Citations (Custom) */
    .citation {
      color: var(--color-accent);
      cursor: pointer;
      font-weight: 500;
      text-decoration: underline;
      text-decoration-style: dotted;
      transition: all 0.2s;
    }
    .citation:hover {
      color: var(--color-accent-dark);
      background-color: var(--color-accent-subtle);
      border-radius: 4px;
    }
  `],
    encapsulation: ViewEncapsulation.None
})
export class MarkdownDisplayComponent {
    content = input.required<string>();
    citationClick = output<string>();
    sanitizer = inject(DomSanitizer);

    sanitizedContent = signal<SafeHtml>('');

    constructor() {
        effect(async () => {
            const raw = this.content();
            if (!raw) {
                this.sanitizedContent.set('');
                return;
            }

            // Parse Markdown
            let html = await marked.parse(raw);

            // Process Citations: [Source: filename]
            // Regex matches [Source: anything] and wraps it
            html = html.replace(/\[Source:\s*([^\]]+)\]/g, (match, sourceName) => {
                return `<span class="citation" data-source="${sourceName.trim()}">${match}</span>`;
            });

            this.sanitizedContent.set(this.sanitizer.bypassSecurityTrustHtml(html));
        });
    }

    handleContentClick(event: MouseEvent) {
        const target = event.target as HTMLElement;
        const citation = target.closest('.citation');

        if (citation) {
            const sourceName = citation.getAttribute('data-source');
            if (sourceName) {
                this.citationClick.emit(sourceName);
                event.stopPropagation();
            }
        }
    }
}
