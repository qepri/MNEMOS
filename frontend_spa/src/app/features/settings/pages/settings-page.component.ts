import { Component, signal, inject, OnInit, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { SettingsService } from '@services/settings.service';
import { ChatPreferences, SystemPrompt } from '@core/models';

@Component({
    selector: 'app-settings-page',
    standalone: true,
    imports: [CommonModule, RouterLink, FormsModule],
    host: { class: 'flex flex-col h-full w-full' },
    templateUrl: './settings-page.component.html',
    styleUrl: './settings-page.component.css'
})
export class SettingsPage implements OnInit {
    settingsService = inject(SettingsService);

    activeTab = signal<'models' | 'discover' | 'import' | 'chat'>('models');

    // Prompt Modal
    isPromptModalOpen = signal<boolean>(false);
    editingPromptId = signal<string | null>(null);
    promptForm = signal<{ title: string, content: string }>({ title: '', content: '' });

    // Import State
    importFiles = signal<string[]>([]);
    importModelName = signal<string>('');
    selectedImportFile = signal<string>('');

    // Discover State
    searchQuery = signal<string>('');
    searchResults = signal<any[]>([]);

    constructor() { }

    ngOnInit() {
        this.loadAllData();
    }

    async loadAllData() {
        await Promise.all([
            this.settingsService.loadModels(),
            this.settingsService.loadCurrentModel(),
            this.settingsService.loadChatPreferences(),
            this.settingsService.loadSystemPrompts()
        ]);
    }

    switchTab(tab: 'models' | 'discover' | 'import' | 'chat') {
        this.activeTab.set(tab);
        if (tab === 'import') {
            this.scanImports();
        } else if (tab === 'discover') {
            this.searchLibrary();
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
        try {
            const res = await this.settingsService.searchLibrary(this.searchQuery());
            this.searchResults.set(res.models);
        } catch (err) {
            console.error(err);
        }
    }

    async handlePullModel(modelName: string) {
        try {
            await this.settingsService.pullModel({ model: modelName });
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

    // Chat Preferences
    async handleSaveChatPreferences() {
        const prefs = this.settingsService.chatPreferences();
        if (prefs) {
            await this.settingsService.saveChatPreferences(prefs);
            alert('Settings saved');
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
