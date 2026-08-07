import { Component, Input, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { LlmAvailabilityService } from '@services/llm-availability.service';

/**
 * Shown in place of a feature that needs a language model.
 *
 * MNEMOS indexes and searches without one, so an absent LLM is a supported
 * state rather than an error. The point of this component is to make that
 * legible: an empty graph canvas reads as a bug, this reads as a choice the
 * user hasn't made yet.
 *
 * Deliberately not a "disabled" tooltip - tooltips are invisible on touch, and
 * mobile access over the LAN is a supported use case.
 */
@Component({
    selector: 'app-llm-dormant',
    standalone: true,
    imports: [CommonModule, RouterLink],
    template: `
    <div class="flex flex-col items-center justify-center text-center p-8 h-full min-h-[12rem] gap-3">
      <div class="text-4xl opacity-40" aria-hidden="true">
        {{ availability.availability().state === 'unreachable' ? '🔌' : '✨' }}
      </div>

      <h3 class="text-lg font-semibold text-base-content">{{ heading }}</h3>

      <p class="text-sm text-secondary max-w-md">
        {{ availability.dormantMessage() }}
      </p>

      @if (availability.availability().state === 'unreachable') {
        <p class="text-xs text-secondary/70 max-w-md">
          Your documents are still indexed and searchable — only this feature is waiting.
        </p>
      }

      <div class="flex gap-2 mt-2">
        <a routerLink="/settings" [queryParams]="{ tab: 'chat', create: 'custom-connection' }" class="btn btn-sm btn-primary">Connect a model</a>
        <button class="btn btn-sm btn-ghost" (click)="recheck()" [disabled]="checking">
          {{ checking ? 'Checking…' : 'Check again' }}
        </button>
      </div>
    </div>
  `
})
export class LlmDormantComponent {
    availability = inject(LlmAvailabilityService);

    @Input() heading: string = 'Needs a language model';

    checking = false;

    async recheck() {
        this.checking = true;
        try {
            // force=true bypasses the server-side cache: the user has probably
            // just started their server and expects an immediate answer.
            await this.availability.refresh(true);
        } finally {
            this.checking = false;
        }
    }
}
