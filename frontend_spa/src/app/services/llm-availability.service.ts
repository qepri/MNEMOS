import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ApiEndpoints } from '@core/constants/api-endpoints';

/**
 * Three states, not two. "No provider configured" and "configured but the
 * server isn't running" need different messages: telling someone to install
 * Ollama when Ollama is installed but stopped is a wrong instruction.
 */
export type LlmState = 'unknown' | 'unconfigured' | 'unreachable' | 'available';

export interface LlmAvailability {
    state: LlmState;
    provider: string | null;
    endpoint: string | null;
    detail: string | null;
    checked_at?: string;
}

@Injectable({ providedIn: 'root' })
export class LlmAvailabilityService {
    private http = inject(HttpClient);

    availability = signal<LlmAvailability>({
        state: 'unknown',
        provider: null,
        endpoint: null,
        detail: null,
    });

    /**
     * True only when we know a model is reachable. 'unknown' is deliberately
     * falsy: before the first check completes, show the dormant state rather
     * than a chat box that will fail on submit.
     */
    isAvailable = computed(() => this.availability().state === 'available');
    isDormant = computed(() => {
        const s = this.availability().state;
        return s === 'unconfigured' || s === 'unreachable';
    });

    /** Message for a dormant view. The distinction is the whole point. */
    dormantMessage = computed(() => {
        const a = this.availability();
        if (a.state === 'unreachable') {
            return a.endpoint
                ? `MNEMOS can't reach your LLM server at ${a.endpoint}. Start it, or point MNEMOS somewhere else in Settings.`
                : `MNEMOS can't reach your LLM server. Start it, or check the endpoint in Settings.`;
        }
        return `This needs a language model. Connect one in Settings to enable it — your documents stay indexed and searchable either way.`;
    });

    constructor() {
        // ponytail: one fetch at startup plus an explicit "Check again" button,
        // rather than polling. The server caches for 30s anyway, and the user
        // knows when they started their model server better than a timer does.
        void this.refresh();
    }

    async refresh(force = false): Promise<LlmAvailability> {
        const url = force
            ? `${ApiEndpoints.SETTINGS_LLM_AVAILABILITY}?force=true`
            : ApiEndpoints.SETTINGS_LLM_AVAILABILITY;
        try {
            const result = await firstValueFrom(this.http.get<LlmAvailability>(url));
            this.availability.set(result);
            return result;
        } catch {
            // The endpoint itself is down - distinct from the LLM being down,
            // but from the user's point of view the features are equally off.
            const fallback: LlmAvailability = {
                state: 'unconfigured',
                provider: null,
                endpoint: null,
                detail: null,
            };
            this.availability.set(fallback);
            return fallback;
        }
    }
}
