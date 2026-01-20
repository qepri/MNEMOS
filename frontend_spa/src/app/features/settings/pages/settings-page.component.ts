import { Component, signal, inject, OnInit, computed, viewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { SettingsService } from '@services/settings.service';
import { ChatPreferences, SystemPrompt } from '@core/models';
import { ProgressBarComponent } from '@shared/components/progress-bar/progress-bar.component';
import { LlmSelectorComponent } from '@shared/components/llm-selector/llm-selector.component';
import { ToastrService } from 'ngx-toastr';

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
    toastr = inject(ToastrService);
    // Use template refs to distinguish
    chatSelector = viewChild<LlmSelectorComponent>('chatSelector');
    memorySelector = viewChild<LlmSelectorComponent>('memorySelector');

    activeTab = signal<'models' | 'discover' | 'import' | 'chat' | 'voice'>('models');

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



    // Helper to get active custom connection for transcription
    getTranscriptionConnection() {
        const providerId = this.settingsService.chatPreferences()?.transcription_provider;
        if (!providerId || ['local', 'groq', 'openai', 'deepgram'].includes(providerId)) return null;
        return this.settingsService.llmConnections().find(c => c.id === providerId);
    }

    // Chat Preferences
    async handleSaveChatPreferences() {
        const currentPrefs = this.settingsService.chatPreferences();
        if (!currentPrefs) return;

        // 1. Get Chat LLM settings
        const chatSel = this.chatSelector();
        let chatUpdate: any = {};
        let ollamaModelToSet: string | undefined;

        try {
            if (chatSel) {
                const snapshot = chatSel.getSnapshot();

                // Unified Save: If user is editing a custom connection, save it first
                if (snapshot.llm_provider === 'custom') {
                    // Check if form is valid (naive check via internal signals logic or just try save)
                    // The saveConnection method in child throws if invalid? No, it just errors.
                    // Ideally we check validity. 
                    // Accessing internal computed/signals: chatSel.connForm.name(), etc.
                    const name = chatSel.connForm.name();
                    const url = chatSel.connForm.baseUrl();
                    const key = chatSel.connForm.apiKey();
                    const isNew = chatSel.selectedConnectionId() === 'new';
                    const defaultModel = chatSel.connForm.defaultModel();

                    // Only attempt save if it looks valid to avoid error toasts for half-filled forms
                    if (name && url) {
                        try {
                            await chatSel.saveConnection();
                            // Fetch fresh snapshot after save (in case ID changed from 'new' to 'uuid')
                            const newSnapshot = chatSel.getSnapshot();
                            Object.assign(snapshot, newSnapshot);

                            this.toastr.info('Connection details updated automatically', 'Unified Save');
                        } catch (e) {
                            console.warn("Auto-save of connection failed", e);
                            // Don't block main save, but maybe warn?
                        }
                    }
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
            this.toastr.success('Settings saved successfully');
        } catch (e: any) {
            console.error(e);
            const msg = e.error?.error || 'Failed to save settings. Please check your inputs.';
            this.toastr.error(msg, 'Error saving settings');
        }
    }
    // Import State
    importFiles = signal<string[]>([]);
    importModelName = signal<string>('');
    selectedImportFile = signal<string>('');

    // Heuristic to check if file is already imported
    getImportStatus(filename: string): { text: string, class: string } {
        const basename = filename.toLowerCase().replace('.gguf', '');
        const models = this.settingsService.models()?.models || [];

        // Check if any model name contains the basename (or vice versa, roughly)
        // User typically names it similarly. 
        // e.g. file: "DeepSeek-R1.gguf", model: "deepseek-r1:latest"
        const isUrl = (s: string) => s.includes(':'); // simplistic check for "name:tag"

        const exists = models.some(m => {
            const mName = m.name.toLowerCase();
            const mBase = mName.split(':')[0]; // ignore tag
            return mName.includes(basename) || basename.includes(mBase);
        });

        if (exists) {
            return { text: 'Already imported (Ready to use)', class: 'text-success' };
        }
        return { text: 'Ready to import', class: 'text-secondary' };
    }

    selectImportFile(file: string) {
        this.selectedImportFile.set(file);
        // Auto-populate model name: remove extension, lowercase
        const name = file.replace(/\.gguf$/i, '').toLowerCase();
        this.importModelName.set(name);
    }

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
            this.settingsService.loadConnections(),
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

                    // Parse progress_line if it exists (It's a JSON string from backend)
                    if (merged.progress_line && typeof merged.progress_line === 'string') {
                        try {
                            const progressData = JSON.parse(merged.progress_line);
                            if (progressData.total && progressData.completed) {
                                merged.total = progressData.total;
                                merged.completed = progressData.completed;
                                // Calculate progress immediately for consistency
                                merged.progress = (merged.completed / merged.total) * 100;
                            }
                            // Also update status message if available
                            if (progressData.status) {
                                merged.status = progressData.status; // e.g. "pulling sha256..."
                            }
                        } catch (e) {
                            console.warn("Failed to parse progress_line", e);
                        }
                    }

                    // Normalize Status for UI
                    // If Celery says SUCCESS but result has error -> Error
                    if (merged.status === 'SUCCESS' && merged.result && merged.result.status === 'error') {
                        merged.status = 'failure';
                        merged.error = merged.result.error;
                    } else if (merged.status === 'SUCCESS') {
                        merged.status = 'success';
                        merged.progress = 100;

                        // Auto-dismiss success after 5 seconds
                        // First check if we already scheduled it
                        if (!currentDownloads[pull.task_id]?.dismissScheduled) {
                            merged.dismissScheduled = true;
                            // Trigger model refresh so new model appears in list
                            this.settingsService.loadModels();

                            setTimeout(() => {
                                const now = { ...this.activeDownloads() };
                                // Only delete if it's still success (user might have deleted it manually)
                                if (now[pull.task_id] && now[pull.task_id].status === 'success') {
                                    delete now[pull.task_id];
                                    this.activeDownloads.set(now);
                                    // Also try to clean up backend if possible, but frontend-only dismissal is fine for UX
                                    this.settingsService.deletePull(pull.task_id).catch(() => { });
                                }
                            }, 5000);
                        } else {
                            // Preserve scheduled flag
                            merged.dismissScheduled = true;
                        }

                    } else if (merged.status === 'FAILURE') {
                        merged.status = 'failure';
                    }

                    currentDownloads[pull.task_id] = merged;
                    hasChanges = true;
                } catch (e) {
                    console.error(`Failed to poll task ${pull.task_id}`, e);
                }
            }

            // Remove downloads that are no longer active (completed/failed and removed from backend list)
            // Filter out keys in currentDownloads that are not in activePulls
            const activeIds = new Set(pullsArray.map(p => p.task_id));
            Object.keys(currentDownloads).forEach(id => {
                // If it's not in backend list AND not scheduled for dismissal (meaning it's gone abruptly)
                // Or if it IS in backend list but we track it locally
                if (!activeIds.has(id)) {
                    // If it was validly removed (e.g. by delete button), let it go.
                    // But if it finished and backend cleared it, we might want to show it?
                    // For now, sync with backend, except if we are holding it for dismissal
                    if (!currentDownloads[id].dismissScheduled) {
                        delete currentDownloads[id];
                        hasChanges = true;
                    }
                }
            });

            if (hasChanges) {
                this.activeDownloads.set(currentDownloads);
            }

        } catch (e) {
            console.error('Polling failed', e);
        }
    }

    switchTab(tab: 'models' | 'discover' | 'import' | 'chat' | 'voice') {
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
            this.selectImportFile(files[0]);
        }
    }

    async handleFileUpload(event: Event) {
        const input = event.target as HTMLInputElement;
        if (!input.files || input.files.length === 0) return;

        const file = input.files[0];
        if (!file.name.toLowerCase().endsWith('.gguf')) {
            this.toastr.error('Only .gguf files are allowed', 'Invalid File');
            return;
        }

        const taskId = `upload-${Date.now()}`;
        this.activeDownloads.update(d => ({
            ...d,
            [taskId]: {
                task_id: taskId,
                model: file.name,
                status: 'uploading',
                progress: 0,
                is_import: true
            }
        }));

        this.toastr.info(`Uploading ${file.name}...`, 'Upload Started');

        try {
            const res = await this.settingsService.uploadModel(file);
            if (res.success) {
                this.toastr.success('File uploaded successfully', 'Upload Complete');
                await this.scanImports(); // Refresh list
                this.selectImportFile(res.filename); // Auto-select new file

                this.activeDownloads.update(d => ({
                    ...d,
                    [taskId]: { ...d[taskId], status: 'success', progress: 100, dismissScheduled: true }
                }));

                setTimeout(() => {
                    this.activeDownloads.update(d => {
                        const next = { ...d };
                        delete next[taskId];
                        return next;
                    });
                }, 5000);
            }
        } catch (error) {
            console.error(error);
            this.toastr.error('Failed to upload file', 'Upload Failed');
            this.activeDownloads.update(d => ({
                ...d,
                [taskId]: { ...d[taskId], status: 'failure' }
            }));
        } finally {
            input.value = ''; // Reset input
        }
    }

    async handleImportModel() {
        if (!this.selectedImportFile() || !this.importModelName()) return;

        const modelName = this.importModelName();
        const taskId = `import-${Date.now()}`;

        // Optimistic UI: Add to active downloads to show progress/spinner
        this.activeDownloads.update(d => ({
            ...d,
            [taskId]: {
                task_id: taskId,
                model: modelName,
                status: 'importing', // Custom status, UI should handle 'importing' or generic string
                progress: 0,
                is_import: true
            }
        }));

        this.toastr.info(`Importing ${modelName}...`, 'Import Started');

        try {
            await this.settingsService.importModel(this.selectedImportFile(), modelName);

            // Update to success
            this.activeDownloads.update(d => ({
                ...d,
                [taskId]: { ...d[taskId], status: 'success', progress: 100, dismissScheduled: true }
            }));

            this.toastr.success(`Successfully imported ${modelName}`, 'Import Complete');
            this.importModelName.set('');

            // Refresh models list
            await this.settingsService.loadModels();

            // Clean up task after delay
            setTimeout(() => {
                this.activeDownloads.update(d => {
                    const next = { ...d };
                    delete next[taskId];
                    return next;
                });
            }, 5000);

            this.switchTab('models');

        } catch (err: any) {
            console.error(err);
            // Update to failure
            this.activeDownloads.update(d => ({
                ...d,
                [taskId]: { ...d[taskId], status: 'failure' }
            }));
            const msg = err.error?.error || 'Failed to import model';
            this.toastr.error(msg, 'Import Failed');
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

    // GGUF Direct Download
    // GGUF Direct Download
    isGgufModalOpen = signal<boolean>(false);
    ggufFiles = signal<{ filename: string, size_mb: number, quantization: string }[]>([]);
    loadingGgufFiles = signal<boolean>(false);
    selectedRepoId = signal<string | null>(null);
    hardwareInfo = signal<{ ram_available: number, vram_available: number, gpu_name: string | null } | null>(null);

    async openGgufModal(repoId: string) {
        this.selectedRepoId.set(repoId);
        this.ggufFiles.set([]);
        this.loadingGgufFiles.set(true);
        this.isGgufModalOpen.set(true);
        this.hardwareInfo.set(null);

        try {
            const [files, hw] = await Promise.all([
                this.settingsService.listRepoFiles(repoId),
                this.settingsService.getHardwareInfo()
            ]);
            this.ggufFiles.set(files);
            this.hardwareInfo.set(hw);
        } catch (error) {
            this.toastr.error('Failed to load file list from Hugging Face');
            this.closeGgufModal();
        } finally {
            this.loadingGgufFiles.set(false);
        }
    }

    closeGgufModal() {
        this.isGgufModalOpen.set(false);
        this.selectedRepoId.set(null);
    }

    async handlePullGguf(file: any) {
        const repo = this.selectedRepoId();
        if (!repo) return;

        // Construct a friendly name: "qwen2.5-7b-instruct-q4"
        // Simple heuristic: repo name + quantization
        const shortName = repo.split('/').pop()?.toLowerCase() || 'model';
        const modelName = `${shortName}-${file.quantization.toLowerCase()}`;

        if (!confirm(`Download ${file.filename} (${file.size_mb.toFixed(0)} MB) as "${modelName}"?`)) return;

        try {
            await this.settingsService.pullModelGguf(repo, file.filename, modelName);
            this.toastr.success(`Download started for ${modelName}`, 'Download Queued');
            this.closeGgufModal();
            // Switch to models tab to see progress? Or active downloads?
            // Actually stay here is fine.
        } catch (error) {
            this.toastr.error('Failed to start download');
        }
    }
}
