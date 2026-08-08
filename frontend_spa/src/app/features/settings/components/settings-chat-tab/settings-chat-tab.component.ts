import { Component, computed, inject, signal, viewChild, input, effect, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { SettingsService } from '@services/settings.service';
import { ToastrService } from 'ngx-toastr';
import { ChatPreferences } from '@core/models';
import { LlmSelectorComponent } from '@shared/components/llm-selector/llm-selector.component';
import { LlmGenerationParamsComponent } from '../llm-generation-params/llm-generation-params.component';
import { SettingsSystemPromptsComponent } from '../settings-system-prompts/settings-system-prompts.component';

@Component({
    selector: 'app-settings-chat-tab',
    standalone: true,
    imports: [CommonModule, FormsModule, LlmSelectorComponent, LlmGenerationParamsComponent, SettingsSystemPromptsComponent],
    templateUrl: './settings-chat-tab.component.html'
})
export class SettingsChatTabComponent {
    settingsService = inject(SettingsService);
    toastr = inject(ToastrService);
    private http = inject(HttpClient);

    // Re-embed task state
    reembedState = signal<string | null>(null);   // null | 'PENDING' | 'PROGRESS' | 'SUCCESS' | 'FAILURE'
    reembedStage = signal<string>('');             // 'chunks' | 'concepts'
    reembedDone = signal<number>(0);
    reembedTotal = signal<number>(0);
    private reembedPoller: any = null;

    async handleReembedLibrary() {
        const ok = window.confirm(
            'Re-embed ALL documents and concepts with the current embedding model?\n\n' +
            'This can take minutes to hours depending on corpus size.\n' +
            'It is strongly recommended to back up your database first ' +
            '(see CLAUDE.md for the pg_dump command).\n\n' +
            'Continue?'
        );
        if (!ok) return;

        try {
            const res: any = await firstValueFrom(
                this.http.post('/api/settings/reembed', {})
            );
            this.toastr.info(`Re-embedding to ${res.target_model} (${res.target_dimension}d)`, 'Re-embed started');
            this.pollReembed(res.task_id);
        } catch (e: any) {
            this.toastr.error(e.error?.error || 'Failed to start re-embed', 'Error');
        }
    }

    private pollReembed(taskId: string) {
        if (this.reembedPoller) clearInterval(this.reembedPoller);
        this.reembedState.set('PENDING');
        this.reembedPoller = setInterval(async () => {
            try {
                const r: any = await firstValueFrom(
                    this.http.get(`/api/settings/reembed/status/${taskId}`)
                );
                this.reembedState.set(r.state);
                if (r.stage) this.reembedStage.set(r.stage);
                if (typeof r.done === 'number') this.reembedDone.set(r.done);
                if (typeof r.total === 'number') this.reembedTotal.set(r.total);

                if (r.state === 'SUCCESS') {
                    clearInterval(this.reembedPoller);
                    this.reembedPoller = null;
                    this.toastr.success('Library re-embedded successfully', 'Done');
                } else if (r.state === 'FAILURE') {
                    clearInterval(this.reembedPoller);
                    this.reembedPoller = null;
                    this.toastr.error(r.error || 'Re-embed failed', 'Error');
                }
            } catch {
                // transient network errors — keep polling
            }
        }, 2000);
    }

    reembedProgressPct = computed(() => {
        const t = this.reembedTotal();
        const d = this.reembedDone();
        return t > 0 ? Math.round((d / t) * 100) : 0;
    });

    get reembedRunning(): boolean {
        const s = this.reembedState();
        return s === 'PENDING' || s === 'PROGRESS';
    }

    chatSelector = viewChild<LlmSelectorComponent>('chatSelector');
    memorySelector = viewChild<LlmSelectorComponent>('memorySelector');
    hypergraphSelector = viewChild<LlmSelectorComponent>('hypergraphSelector');
    aiProviderSection = viewChild<ElementRef<HTMLElement>>('aiProviderSection');

    // Set by a `?create=custom-connection` link (e.g. the dormant-state CTA):
    // opens straight onto a blank connection form instead of just the tab.
    autoCreateConnection = input(false);
    private didAutoCreate = false;

    constructor() {
        effect(() => {
            const selector = this.chatSelector();
            // Wait for the real saved preferences to arrive first: LlmSelectorComponent
            // has its own effect that re-syncs selectedProvider from `preferences()`
            // whenever it changes, and chatPreferences() starts null then resolves
            // async. Firing before that lands would set 'custom' only to have it
            // clobbered back to the saved provider a moment later.
            const prefsLoaded = !!this.settingsService.chatPreferences();
            if (!this.autoCreateConnection() || !selector || !prefsLoaded || this.didAutoCreate) return;
            this.didAutoCreate = true;

            // Deferred a tick so this runs after the prefs-sync effect above has
            // already flushed for this change, rather than racing it.
            setTimeout(() => {
                selector.updateProvider('custom');
                selector.selectedConnectionId.set('new');
                this.aiProviderSection()?.nativeElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
        }, { allowSignalWrites: true });
    }

    memoryLlmPreferences = computed(() => {
        const prefs = this.settingsService.chatPreferences();
        if (!prefs) return null;
        return {
            ...prefs,
            llm_provider: prefs.memory_provider,
            selected_llm_model: prefs.memory_llm_model
        } as ChatPreferences;
    });

    hypergraphLlmPreferences = computed(() => {
        const prefs = this.settingsService.chatPreferences();
        if (!prefs) return null;
        return {
            ...prefs,
            llm_provider: prefs.hypergraph_llm_provider || 'llamacpp',
            selected_llm_model: prefs.hypergraph_llm_model || undefined
        } as ChatPreferences;
    });

    getTranscriptionConnection() {
        const providerId = this.settingsService.chatPreferences()?.transcription_provider;
        if (!providerId || ['local', 'groq', 'openai', 'deepgram'].includes(providerId)) return null;
        return this.settingsService.llmConnections().find(c => c.id === providerId);
    }

    async handleSaveChatPreferences() {
        const currentPrefs = this.settingsService.chatPreferences();
        if (!currentPrefs) return;

        const chatSel = this.chatSelector();
        let chatUpdate: any = {};

        try {
            if (chatSel) {
                const snapshot = chatSel.getSnapshot();

                if (snapshot.llm_provider === 'custom') {
                    const name = chatSel.connForm.name();
                    const url = chatSel.connForm.baseUrl();

                    if (name && url) {
                        try {
                            await chatSel.saveConnection();
                            const newSnapshot = chatSel.getSnapshot();
                            Object.assign(snapshot, newSnapshot);
                            this.toastr.info('Connection details updated automatically', 'Unified Save');
                        } catch (e) {
                            console.warn("Auto-save of connection failed", e);
                        }
                    }
                }

                chatUpdate = snapshot;
            }

            const memSel = this.memorySelector();
            let memUpdate: any = {};

            if (memSel) {
                const snapshot = memSel.getSnapshot();
                memUpdate.memory_provider = snapshot.llm_provider;
                memUpdate.memory_llm_model = snapshot.selected_llm_model;

                if (snapshot.openai_api_key) memUpdate.openai_api_key = snapshot.openai_api_key;
                if (snapshot.anthropic_api_key) memUpdate.anthropic_api_key = snapshot.anthropic_api_key;
                if (snapshot.groq_api_key) memUpdate.groq_api_key = snapshot.groq_api_key;
                if (snapshot.custom_api_key) memUpdate.custom_api_key = snapshot.custom_api_key;
                if (snapshot.local_llm_base_url) memUpdate.local_llm_base_url = snapshot.local_llm_base_url;
            }

            const hyperSel = this.hypergraphSelector();
            let hyperUpdate: any = {};

            if (hyperSel) {
                const snapshot = hyperSel.getSnapshot();
                hyperUpdate.hypergraph_llm_provider = snapshot.llm_provider;
                hyperUpdate.hypergraph_llm_model = snapshot.selected_llm_model;

                if (snapshot.openai_api_key) hyperUpdate.openai_api_key = snapshot.openai_api_key;
                if (snapshot.anthropic_api_key) hyperUpdate.anthropic_api_key = snapshot.anthropic_api_key;
                if (snapshot.groq_api_key) hyperUpdate.groq_api_key = snapshot.groq_api_key;
                if (snapshot.custom_api_key) hyperUpdate.custom_api_key = snapshot.custom_api_key;
                if (snapshot.local_llm_base_url) hyperUpdate.local_llm_base_url = snapshot.local_llm_base_url;
            }

            const finalPrefs: ChatPreferences = {
                ...currentPrefs,
                ...chatUpdate,
                ...memUpdate,
                ...hyperUpdate
            };

            await this.settingsService.saveChatPreferences(finalPrefs);

            this.toastr.success('Settings saved successfully');
        } catch (e: any) {
            console.error(e);
            const msg = e.error?.error || 'Failed to save settings. Please check your inputs.';
            this.toastr.error(msg, 'Error saving settings');
        }
    }
}
