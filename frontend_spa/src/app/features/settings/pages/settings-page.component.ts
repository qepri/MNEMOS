import { Component, signal, inject, OnInit, computed, DestroyRef } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { RouterLink, ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { SettingsService } from '@services/settings.service';
import { ToastrService } from 'ngx-toastr';
import { AppRoutes } from '@core/constants/app-routes';

import { PluginsSettingsComponent } from '../components/plugins-settings/plugins-settings.component';
import { SettingsActiveDownloadsComponent } from '../components/settings-active-downloads/settings-active-downloads.component';
import { SettingsModelsTabComponent } from '../components/settings-models-tab/settings-models-tab.component';
import { SettingsDiscoverTabComponent } from '../components/settings-discover-tab/settings-discover-tab.component';
import { SettingsManageTabComponent } from '../components/settings-manage-tab/settings-manage-tab.component';
import { SettingsVoiceTabComponent } from '../components/settings-voice-tab/settings-voice-tab.component';
import { SettingsChatTabComponent } from '../components/settings-chat-tab/settings-chat-tab.component';
import { LlmBackfillCardComponent } from '../components/llm-backfill-card.component';

@Component({
    selector: 'app-settings-page',
    standalone: true,
    imports: [
        CommonModule,
        RouterLink,
        FormsModule,
        PluginsSettingsComponent,
        SettingsActiveDownloadsComponent,
        SettingsModelsTabComponent,
        SettingsDiscoverTabComponent,
        SettingsManageTabComponent,
        SettingsVoiceTabComponent,
        SettingsChatTabComponent,
        LlmBackfillCardComponent
    ],
    host: { class: 'flex flex-col h-full w-full' },
    templateUrl: './settings-page.component.html',
    styleUrl: './settings-page.component.css'
})
export class SettingsPage implements OnInit {
    settingsService = inject(SettingsService);
    toastr = inject(ToastrService);
    private route = inject(ActivatedRoute);
    private router = inject(Router);
    private destroyRef = inject(DestroyRef);
    protected readonly AppRoutes = AppRoutes;

    private static readonly TABS = ['models', 'discover', 'manage', 'chat', 'voice', 'plugins'] as const;
    activeTab = signal<typeof SettingsPage.TABS[number]>('models');

    ggufModels = signal<any[]>([]);
    currentGgufModel = signal<string>('');

    importFiles = signal<string[]>([]);
    importModelName = signal<string>('');
    selectedImportFile = signal<string>('');

    searchQuery = signal<string>('');
    searchResults = signal<any[]>([]);
    isSearching = signal<boolean>(false);

    activeDownloads = signal<{ [key: string]: any }>({});
    activeDownloadsList = computed(() => Object.values(this.activeDownloads()));
    private pollInterval: any;

    isGgufModalOpen = signal<boolean>(false);
    ggufFiles = signal<{ filename: string, size_mb: number, quantization: string }[]>([]);
    loadingGgufFiles = signal<boolean>(false);
    selectedRepoId = signal<string | null>(null);
    hardwareInfo = signal<{ ram_available: number, vram_available: number, gpu_name: string | null } | null>(null);

    // ?create=custom-connection additionally opens the chat tab's provider
    // selector straight onto a blank "Create New Connection" form, so a link
    // can point at the exact field the user needs rather than just the tab.
    openCreateConnection = signal(false);

    ngOnInit() {
        // ?tab=chat lets links (e.g. "Connect a model") open Settings on the
        // right tab directly, instead of always landing on Installed Models.
        // A *subscription*, not a one-time snapshot read: Angular reuses this
        // component instance for same-route navigations (e.g. a button inside
        // Settings itself linking chat -> discover), so a snapshot taken once
        // in ngOnInit would miss those and silently do nothing.
        this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(params => {
            const requestedTab = params.get('tab');
            if ((SettingsPage.TABS as readonly string[]).includes(requestedTab ?? '')
                && requestedTab !== this.activeTab()) {
                this.switchTab(requestedTab as typeof SettingsPage.TABS[number]);
            }
            this.openCreateConnection.set(params.get('create') === 'custom-connection');
        });

        this.loadAllData();
        this.startDownloadPolling();
    }

    ngOnDestroy() {
        if (this.pollInterval) clearInterval(this.pollInterval);
    }

    async loadAllData() {
        await this.loadGgufModels();
        await Promise.all([
            this.settingsService.loadChatPreferences(),
            this.settingsService.loadSystemPrompts(),
            this.settingsService.loadMemories(),
            this.settingsService.loadConnections()
        ]);
    }

    async loadGgufModels() {
        try {
            const response = await this.settingsService.getLlamacppModels();
            this.ggufModels.set(response.models);
            const prefs = this.settingsService.chatPreferences();
            if (prefs?.llm_provider === 'llamacpp' && prefs?.selected_llm_model) {
                this.currentGgufModel.set(prefs.selected_llm_model);
            }
        } catch (e) {
            console.error('Failed to load GGUF models:', e);
        }
    }

    async startDownloadPolling() {
        this.pollDownloads();
        this.pollInterval = setInterval(() => this.pollDownloads(), 2000);
    }

    async pollDownloads() {
        try {
            const activePulls = await this.settingsService.getActivePulls();

            const currentDownloads = { ...this.activeDownloads() };
            let hasChanges = false;

            let pullsArray: any[] = [];
            if (Array.isArray(activePulls)) {
                pullsArray = activePulls;
            } else if (activePulls && Array.isArray((activePulls as any).active_tasks)) {
                pullsArray = (activePulls as any).active_tasks;
            }

            for (const pull of pullsArray) {
                try {
                    let merged = { ...pull };
                    if (merged.progress_line && typeof merged.progress_line === 'string') {
                        try {
                            const progressData = JSON.parse(merged.progress_line);
                            if (progressData.total && progressData.completed) {
                                merged.total = progressData.total;
                                merged.completed = progressData.completed;
                                merged.progress = (merged.completed / merged.total) * 100;
                            }
                            if (progressData.status) {
                                merged.status = progressData.status;
                            }
                        } catch (e) {
                            console.warn("Failed to parse progress_line", e);
                        }
                    }

                    if (merged.status === 'SUCCESS' && merged.result && merged.result.status === 'error') {
                        merged.status = 'failure';
                        merged.error = merged.result.error;
                    } else if (merged.status === 'SUCCESS') {
                        merged.status = 'success';
                        merged.progress = 100;

                        if (!currentDownloads[pull.task_id]?.dismissScheduled) {
                            merged.dismissScheduled = true;
                            this.settingsService.loadModels();
                            setTimeout(() => {
                                const now = { ...this.activeDownloads() };
                                if (now[pull.task_id] && now[pull.task_id].status === 'success') {
                                    delete now[pull.task_id];
                                    this.activeDownloads.set(now);
                                    this.settingsService.deletePull(pull.task_id).catch(() => { });
                                }
                            }, 5000);
                        } else {
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

            const activeIds = new Set(pullsArray.map(p => p.task_id));
            Object.keys(currentDownloads).forEach(id => {
                if (!activeIds.has(id)) {
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

    switchTab(tab: typeof SettingsPage.TABS[number]) {
        this.activeTab.set(tab);
        // replaceUrl: switching tabs isn't a navigation a user expects "Back" to undo.
        this.router.navigate([], {
            relativeTo: this.route,
            queryParams: { tab },
            queryParamsHandling: 'merge',
            replaceUrl: true
        });
        if (tab === 'manage') {
            this.scanImports();
        } else if (tab === 'discover') {
            if (this.searchResults().length === 0) {
                this.searchLibrary();
            }
        }
    }

    async handleSetCurrentGgufModel(filename: string) {
        try {
            await this.settingsService.saveChatPreferences({
                llm_provider: 'llamacpp',
                selected_llm_model: filename
            });
            this.currentGgufModel.set(filename);
            this.toastr.success(`Model set to ${filename}`);
        } catch (e) {
            console.error('Failed to set GGUF model:', e);
            this.toastr.error('Failed to set model');
        }
    }

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

    async scanImports() {
        const files = await this.settingsService.scanImports();
        this.importFiles.set(files);
        if (files.length > 0) {
            this.selectImportFile(files[0]);
        }
    }

    selectImportFile(file: string) {
        this.selectedImportFile.set(file);
        const name = file.replace(/\.gguf$/i, '').toLowerCase();
        this.importModelName.set(name);
    }

    getImportStatus(filename: string): { text: string, class: string } {
        const basename = filename.toLowerCase().replace('.gguf', '');
        const models = this.settingsService.models()?.models || [];
        const exists = models.some(m => {
            const mName = m.name.toLowerCase();
            const mBase = mName.split(':')[0];
            return mName.includes(basename) || basename.includes(mBase);
        });

        if (exists) {
            return { text: 'Already imported (Ready to use)', class: 'text-success' };
        }
        return { text: 'Ready to import', class: 'text-secondary' };
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
                await this.scanImports();
                this.selectImportFile(res.filename);

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
            input.value = '';
        }
    }

    async handleDeletePull(taskId: string) {
        if (!window.confirm('Are you sure you want to cancel/clear this download?')) return;

        try {
            await this.settingsService.deletePull(taskId);
            const current = { ...this.activeDownloads() };
            delete current[taskId];
            this.activeDownloads.set(current);
        } catch (error) {
            console.error('Failed to delete task', error);
            this.toastr.error('Failed to delete task. Check console.');
        }
    }

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

        const shortName = repo.split('/').pop()?.toLowerCase() || 'model';
        const modelName = `${shortName}-${file.quantization.toLowerCase()}`;

        if (!confirm(`Download ${file.filename} (${file.size_mb.toFixed(0)} MB) as "${modelName}"?`)) return;

        try {
            await this.settingsService.pullModelGguf(repo, file.filename, modelName);
            this.toastr.success(`Download started for ${modelName}`, 'Download Queued');
            this.closeGgufModal();
        } catch (error) {
            this.toastr.error('Failed to start download');
        }
    }
}
