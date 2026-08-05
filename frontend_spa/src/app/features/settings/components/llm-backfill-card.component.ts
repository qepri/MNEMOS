import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ToastrService } from 'ngx-toastr';
import { LlmAvailabilityService } from '@services/llm-availability.service';

interface BackfillStatus {
    needs_summary: number;
    needs_concepts: number;
    total: number;
}

/**
 * Offers to generate summaries and concepts for documents that were indexed
 * before a model was connected.
 *
 * Explicitly a button, never automatic: summarization fans out to five
 * concurrent LLM calls per document, so silently starting this the moment a
 * provider is connected would tie up the user's GPU for a long time without
 * them asking for it.
 */
@Component({
    selector: 'app-llm-backfill-card',
    standalone: true,
    imports: [CommonModule],
    template: `
    @if (availability.isAvailable() && status() && status()!.total > 0) {
      <div class="p-4 rounded-xl border border-divider bg-panel/40 flex flex-col gap-3">
        <div>
          <h3 class="font-semibold text-base-content">Catch up on older documents</h3>
          <p class="text-sm text-secondary mt-1">
            {{ status()!.total }} document{{ status()!.total === 1 ? '' : 's' }} indexed before a
            model was connected {{ status()!.total === 1 ? 'is' : 'are' }} missing
            {{ missingLabel() }}. Generating {{ status()!.total === 1 ? 'it' : 'them' }} reuses the
            existing index — nothing is re-uploaded or re-embedded.
          </p>
        </div>

        <div class="flex items-center gap-2">
          <button class="btn btn-sm btn-primary" (click)="run()" [disabled]="running()">
            {{ running() ? 'Queuing…' : 'Generate now' }}
          </button>
          <button class="btn btn-sm btn-ghost" (click)="load()" [disabled]="running()">Refresh</button>
        </div>

        <p class="text-xs text-secondary/70">
          Runs in the background, one document at a time. Watch progress in the library.
        </p>
      </div>
    }
  `
})
export class LlmBackfillCardComponent implements OnInit {
    private http = inject(HttpClient);
    private toastr = inject(ToastrService);
    availability = inject(LlmAvailabilityService);

    status = signal<BackfillStatus | null>(null);
    running = signal(false);

    ngOnInit() {
        void this.load();
    }

    missingLabel(): string {
        const s = this.status();
        if (!s) return '';
        const parts: string[] = [];
        if (s.needs_summary > 0) parts.push('summaries');
        if (s.needs_concepts > 0) parts.push('concepts');
        return parts.join(' and ');
    }

    async load() {
        try {
            this.status.set(
                await firstValueFrom(this.http.get<BackfillStatus>('/api/documents/llm-backfill'))
            );
        } catch {
            this.status.set(null);
        }
    }

    async run() {
        this.running.set(true);
        try {
            const result: any = await firstValueFrom(
                this.http.post('/api/documents/llm-backfill', {})
            );
            this.toastr.success(`Queued ${result.documents} document(s) for generation`);
            await this.load();
        } catch {
            this.toastr.error('Could not queue backfill');
        } finally {
            this.running.set(false);
        }
    }
}
