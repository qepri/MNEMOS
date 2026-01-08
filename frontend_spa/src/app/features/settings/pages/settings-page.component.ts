import { Component, signal, inject, OnInit, computed, viewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { SettingsService } from '@services/settings.service';
import { ChatPreferences, SystemPrompt } from '@core/models';
import { ProgressBarComponent } from '@shared/components/progress-bar/progress-bar.component';
import { LlmSelectorComponent } from '@shared/components/llm-selector/llm-selector.component';

@Component({
    selector: 'app-settings-page',
    standalone: true,
    imports: [CommonModule, RouterLink, FormsModule, ProgressBarComponent, LlmSelectorComponent],
    host: { class: 'flex flex-col h-full w-full' },
    templateUrl: './settings-page.component.html',
    styleUrl: './settings-page.component.css'
})
export class SettingsPage implements OnInit {
    settingsService = inject(SettingsService);
    // Use template refs to distinguish
    chatSelector = viewChild<LlmSelectorComponent>('chatSelector');
    memorySelector = viewChild<LlmSelectorComponent>('memorySelector');

    activeTab = signal<'models' | 'discover' | 'import' | 'chat'>('models');

    // Proxy for Memory Selector
    // Maps memory_* fields to llm_* fields so LlmSelectorComponent works as is
    memoryLlmPreferences = computed(() => {
        const prefs = this.settingsService.chatPreferences();
        if (!prefs) return null;
        return {
            ...prefs,
            llm_provider: prefs.memory_provider,
            selected_llm_model: prefs.memory_llm_model
        } as ChatPreferences;
    });

    // Prompt Modal
    isPromptModalOpen = signal<boolean>(false);
    editingPromptId = signal<string | null>(null);
    promptForm = signal<{ title: string, content: string }>({ title: '', content: '' });



    // Chat Preferences
    async handleSaveChatPreferences() {
        const currentPrefs = this.settingsService.chatPreferences();
        if (!currentPrefs) return;

        // 1. Get Chat LLM settings
        const chatSel = this.chatSelector();
        let chatUpdate: any = {};
        let ollamaModelToSet: string | undefined;

        if (chatSel) {
            const snapshot = chatSel.getSnapshot();

            // Check if we need to auto-save the custom connection form (Unified Save Request)
            if (snapshot.llm_provider === 'custom') {
                await chatSel.saveConnection();
                // Refresh snapshot after save? saveConnection mostly updates backend state.
                // The prefs still need the connection ID which is in the snapshot.
                // If it was 'new', saveConnection updates selectedConnectionId, so we should re-fetch snapshot?
                // Let's refetch snapshot to be safe.
                const newSnapshot = chatSel.getSnapshot();
                Object.assign(snapshot, newSnapshot);
            }

            ollamaModelToSet = snapshot.ollamaModel;
            delete snapshot.ollamaModel;
            chatUpdate = snapshot;
        }

        // 2. Get Memory LLM settings
        const memSel = this.memorySelector();
        let memUpdate: any = {};

        if (memSel) {
            const snapshot = memSel.getSnapshot();
            // Map back: llm_provider -> memory_provider
            memUpdate.memory_provider = snapshot.llm_provider;
            // Map back: selected_llm_model OR ollamaModel -> memory_llm_model
            memUpdate.memory_llm_model = snapshot.selected_llm_model || snapshot.ollamaModel;

            // Allow updating keys from here too? Yes, keys are global.
            if (snapshot.openai_api_key) memUpdate.openai_api_key = snapshot.openai_api_key;
            if (snapshot.anthropic_api_key) memUpdate.anthropic_api_key = snapshot.anthropic_api_key;
            if (snapshot.groq_api_key) memUpdate.groq_api_key = snapshot.groq_api_key;
            if (snapshot.custom_api_key) memUpdate.custom_api_key = snapshot.custom_api_key;
            if (snapshot.local_llm_base_url) memUpdate.local_llm_base_url = snapshot.local_llm_base_url;
        }

        // Merge updates
        const finalPrefs: ChatPreferences = {
            ...currentPrefs,
            ...chatUpdate,
            ...memUpdate
        };

        await this.settingsService.saveChatPreferences(finalPrefs);

        if (ollamaModelToSet) {
            await this.settingsService.setCurrentModel(ollamaModelToSet);
        }
        alert('Settings saved');
    }
    // Import State
    importFiles = signal<string[]>([]);
    importModelName = signal<string>('');
    selectedImportFile = signal<string>('');

    // Discover State
    searchQuery = signal<string>('');
    searchResults = signal<any[]>([]);
    isSearching = signal<boolean>(false);

    // Download State
    activeDownloads = signal<{ [key: string]: any }>({});
    activeDownloadsList = computed(() => Object.values(this.activeDownloads()));
    private pollInterval: any;

    constructor() { }

    ngOnInit() {
        this.loadAllData();
        this.startDownloadPolling();
    }

    ngOnDestroy() {
        if (this.pollInterval) clearInterval(this.pollInterval);
    }

    async loadAllData() {
        // Load models separately as it might fail if Ollama is down
        try {
            await this.settingsService.loadModels();
        } catch (e) {
            console.warn('Failed to load models (expected if Ollama is down)');
        }

        await Promise.all([
            this.settingsService.loadCurrentModel().catch(() => { }),
            this.settingsService.loadChatPreferences(),
            this.settingsService.loadSystemPrompts(),
            this.settingsService.loadMemories(),
            this.checkOllamaStatus()
        ]);
    }

    async startDownloadPolling() {
        this.pollDownloads(); // Initial check
        this.pollInterval = setInterval(() => this.pollDownloads(), 2000);
    }

    async pollDownloads() {
        try {
            const activePulls = await this.settingsService.getActivePulls(); // Returns array of { task_id, model_name, ... }

            const currentDownloads = { ...this.activeDownloads() };
            let hasChanges = false;

            // Update known downloads or add new ones
            let pullsArray: any[] = [];
            if (Array.isArray(activePulls)) {
                pullsArray = activePulls;
            } else if (activePulls && Array.isArray((activePulls as any).active_tasks)) {
                pullsArray = (activePulls as any).active_tasks;
            }

            for (const pull of pullsArray) {
                // Fetch latest status/progress for this task
                try {
                    // Start with basic pull info
                    let merged = { ...pull };

                    // If backend return includes 'result' or 'error' in pull object (from my python changes), use it

                    // Normalize Status for UI
                    // If Celery says SUCCESS but result has error -> Error
                    if (merged.status === 'SUCCESS' && merged.result && merged.result.status === 'error') {
                        merged.status = 'failure';
                        merged.error = merged.result.error;
                    } else if (merged.status === 'SUCCESS') {
                        merged.status = 'success';
                        merged.progress = 100;
                    } else if (merged.status === 'FAILURE') {
                        merged.status = 'failure';
                    }

                    currentDownloads[pull.task_id] = merged;
                    hasChanges = true;
                } catch (e) {
                    console.error(`Failed to poll task ${pull.task_id}`, e);
                }
            }

            // Remove downloads that are no longer active (completed/failed and removed from backend list) (?)
            // Actually backend keeps them in list if we implemented it that way?
            // Let's assume backend list is the source of truth for "active"
            // But we might want to keep "completed" ones visible for a bit? 
            // For KISS, let's just sync with backend list.

            // Filter out keys in currentDownloads that are not in activePulls
            const activeIds = new Set(pullsArray.map(p => p.task_id));
            Object.keys(currentDownloads).forEach(id => {
                if (!activeIds.has(id)) {
                    // If it was recently completed, maybe keep it?
                    // For now, if it's gone from backend, remove it.
                    delete currentDownloads[id];
                    hasChanges = true;
                }
            });

            if (hasChanges) {
                this.activeDownloads.set(currentDownloads);
            }

            // Specific fix: If we have active downloads that are NOT in the backend list anymore,
            // it means the backend cleaned them up. We should update them to 'completed' or remove them.
            // But if we just remove them, the user won't know they finished.
            // Let's rely on getActivePulls returning even finished tasks as seen in previous backend code analysis.
            // (Backend code: "if status in ['SUCCESS'...] ids_to_remove.append... else active_list.append")
            // Wait, backend explicitly REMOVES success tasks from the returned list!
            // That's bad for UI.
            // Re-reading backend logic:
            // "if status in ['SUCCESS', 'FAILURE', 'REVOKED']: ids_to_remove.append(task_id)"
            // "if status in [...] active_list.append(...)" -> This is in the loop. 
            // It appends to active_list in the `else` block? 
            // Let me re-read backend code carefully.

        } catch (e) {
            console.error('Polling failed', e);
        }
    }

    switchTab(tab: 'models' | 'discover' | 'import' | 'chat') {
        this.activeTab.set(tab);
        if (tab === 'import') {
            this.scanImports();
        } else if (tab === 'discover') {
            // Only search if empty to encourage discovery but avoid re-fetch on every tab switch if not needed?
            // User probably wants to see results if they return.
            if (this.searchResults().length === 0) {
                this.searchLibrary();
            }
        }
    }

    // Models
    async handleDeleteModel(modelName: string) {
        if (!confirm(`Are you sure you want to delete ${modelName}?`)) return;
        await this.settingsService.deleteModel(modelName);
    }

    async handleSetCurrentModel(modelName: string) {
        await this.settingsService.setCurrentModel(modelName);
    }

    // Discover
    async searchLibrary() {
        this.isSearching.set(true);
        try {
            const res = await this.settingsService.searchLibrary(this.searchQuery());
            this.searchResults.set(res.models);
        } catch (err) {
            console.error(err);
        } finally {
            this.isSearching.set(false);
        }
    }

    async handlePullModel(modelName: string) {
        try {
            const res = await this.settingsService.pullModel({ model: modelName });
            // Add to local state immediately to show feedback
            this.activeDownloads.update(d => ({
                ...d,
                [res.task_id]: { task_id: res.task_id, model: modelName, status: 'starting', progress: 0 }
            }));
            alert(`Started pulling ${modelName}`);
        } catch (err) {
            alert('Failed to start pull');
        }
    }

    // Import
    async scanImports() {
        const files = await this.settingsService.scanImports();
        this.importFiles.set(files);
        if (files.length > 0) {
            this.selectedImportFile.set(files[0]);
        }
    }

    async handleImportModel() {
        if (!this.selectedImportFile() || !this.importModelName()) return;

        try {
            await this.settingsService.importModel(this.selectedImportFile(), this.importModelName());
            alert('Import started/completed');
            this.importModelName.set('');
            this.switchTab('models');
        } catch (err) {
            alert('Import failed');
        }
    }

    async handleDeletePull(taskId: string) {
        if (!window.confirm('Are you sure you want to cancel/clear this download?')) return;

        try {
            await this.settingsService.deletePull(taskId);
            // Optimistic update
            const current = { ...this.activeDownloads() };
            delete current[taskId];
            this.activeDownloads.set(current);
        } catch (error) {
            console.error('Failed to delete task', error);
            window.alert('Failed to delete task. Check console.');
        }
    }



    // Ollama Service State
    ollamaStatus = signal<{ status: string; id?: string }>({ status: 'unknown' });
    ollamaInstallProgress = signal<{ status: string; progress?: number; message?: string } | null>(null);

    async checkOllamaStatus() {
        try {
            const status = await this.settingsService.getOllamaStatus();
            this.ollamaStatus.set(status);
        } catch (e) {
            console.error('Failed to check Ollama status', e);
            this.ollamaStatus.set({ status: 'error' });
        }
    }

    async handleStartOllamaService() {
        try {
            this.ollamaInstallProgress.set({ status: 'starting', message: 'Starting Ollama service...' });
            const res = await this.settingsService.startOllamaService();
            this.ollamaStatus.set(res);
            this.ollamaInstallProgress.set(null);
            setTimeout(() => this.loadAllData(), 2000); // Reload models after start
        } catch (e) {
            console.error(e);
            this.ollamaInstallProgress.set({ status: 'error', message: 'Failed to start service' });
        }
    }

    async handleInstallOllamaService() {
        this.ollamaInstallProgress.set({ status: 'starting', message: 'Initializing download...' });

        this.settingsService.installOllamaService().subscribe({
            next: (event: any) => {
                if (event.type === 3) { // HttpEventType.DownloadProgress is 3 (partial text)
                    // Angular handles streaming text weirdly in default HttpClient events
                    // We simplified backend to send NDJSON
                    const partialText = event.partialText;
                    if (partialText) {
                        const lines = partialText.split('\n').filter((l: string) => l.trim());
                        const lastLine = lines[lines.length - 1];
                        try {
                            const data = JSON.parse(lastLine);
                            this.updateInstallProgress(data);
                        } catch (e) { /* ignore parse error for partial chunks */ }
                    }
                }
                else if (typeof event === 'string') {
                    // Sometimes it comes as string if we used certain responseType settings, 
                    // but here we used observe: 'events'
                }
            },
            complete: () => {
                this.ollamaInstallProgress.set(null);
                this.checkOllamaStatus();
            },
            error: (err) => {
                this.ollamaInstallProgress.set({ status: 'error', message: 'Installation failed' });
                console.error(err);
            }
        });
    }

    updateInstallProgress(data: any) {
        if (data.status) {
            this.ollamaInstallProgress.set({
                status: 'downloading',
                message: data.status,
                progress: data.progressDetail?.current ? (data.progressDetail.current / data.progressDetail.total * 100) : 0
            });
        }
    }

    // Prompts
    openPromptModal(prompt?: SystemPrompt) {
        if (prompt) {
            this.editingPromptId.set(prompt.id);
            this.promptForm.set({ title: prompt.title, content: prompt.content });
        } else {
            this.editingPromptId.set(null);
            this.promptForm.set({ title: '', content: '' });
        }
        this.isPromptModalOpen.set(true);
    }

    closePromptModal() {
        this.isPromptModalOpen.set(false);
    }

    async handleSavePrompt() {
        const { title, content } = this.promptForm();
        if (!title || !content) return;

        if (this.editingPromptId()) {
            await this.settingsService.updateSystemPrompt(this.editingPromptId()!, { title, content });
        } else {
            await this.settingsService.createSystemPrompt(title, content);
        }
        this.closePromptModal();
    }

    async handleDeletePrompt(id: string) {
        if (!confirm('Delete this prompt?')) return;
        await this.settingsService.deleteSystemPrompt(id);
    }
}
