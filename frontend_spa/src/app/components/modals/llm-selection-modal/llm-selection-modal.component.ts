import { Component, computed, effect, inject, model, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SettingsService } from '@services/settings.service';
import { ChatPreferences } from '@core/models';

@Component({
    selector: 'app-llm-selection-modal',
    standalone: true,
    imports: [CommonModule, FormsModule],
    templateUrl: './llm-selection-modal.component.html'
})
export class LlmSelectionModalComponent {
    // Inputs
    isVisible = model<boolean>(false);

    // Services
    settingsService = inject(SettingsService);

    // Hardcoded models
    readonly openaiModels = ['gpt-4o', 'gpt-4o-mini', 'gpt-4.5-preview', 'o1-preview', 'o1-mini'];
    readonly anthropicModels = ['claude-3-5-sonnet-latest', 'claude-3-5-haiku-latest', 'claude-3-opus-latest'];
    readonly groqModels = [
        'llama-3.3-70b-versatile',
        'llama-3.1-70b-versatile',
        'llama-3.1-8b-instant',
        'llama3-70b-8192',
        'llama3-8b-8192',
        'gemma2-9b-it',
        'gemma-7b-it',
        'deepseek-r1-distill-llama-70b',
        'openai/gpt-oss-120b',
        'openai/gpt-oss-20b'
    ];

    // Signals for local state (initially populated from settings)
    selectedProvider = signal<string>('ollama');
    apiKey = signal<string>('');
    baseUrl = signal<string>('');
    customModelId = signal<string>('');
    selectedModel = signal<string>(''); // For dropdown selection

    constructor() {
        // Effect to sync state when modal opens
        effect(() => {
            if (this.isVisible()) {
                const prefs = this.settingsService.chatPreferences();
                if (prefs) {
                    // Initialize local state from global preferences without saving
                    this.selectedProvider.set(prefs.llm_provider || 'ollama');
                    this.syncInputsForProvider(prefs.llm_provider || 'ollama', prefs);

                    // Initialize selected model
                    if (prefs.llm_provider === 'ollama') {
                        this.selectedModel.set(this.settingsService.currentModel() || '');
                    } else {
                        this.selectedModel.set(prefs.selected_llm_model || '');
                    }
                }
            }
        });
    }

    // Computed
    currentModels = computed(() => {
        switch (this.selectedProvider()) {
            case 'ollama':
                return this.settingsService.models()?.models.map(m => m.name) || [];
            case 'openai':
                return this.openaiModels;
            case 'anthropic':
                return this.anthropicModels;
            case 'groq':
                return this.groqModels;
            default:
                return [];
        }
    });

    isManualModelInput = computed(() => {
        return ['lm_studio', 'custom'].includes(this.selectedProvider()); // Groq now uses dropdown/select
    });

    isApiKeyRequired = computed(() => {
        return ['openai', 'anthropic', 'groq'].includes(this.selectedProvider());
    });

    // Methods
    closeModal() {
        this.isVisible.set(false);
    }

    syncInputsForProvider(provider: string, prefs: ChatPreferences) {
        // Reset signals first to avoid stale data
        this.apiKey.set('');
        this.baseUrl.set('');
        this.customModelId.set('');
        this.selectedModel.set('');

        switch (provider) {
            case 'openai':
                this.apiKey.set(prefs.openai_api_key || '');
                this.selectedModel.set(prefs.selected_llm_model || '');
                break;
            case 'anthropic':
                this.apiKey.set(prefs.anthropic_api_key || '');
                this.selectedModel.set(prefs.selected_llm_model || '');
                break;
            case 'groq':
                this.apiKey.set(prefs.groq_api_key || '');
                this.selectedModel.set(prefs.selected_llm_model || '');
                break;
            case 'lm_studio':
            case 'custom':
            case 'ollama':
                this.baseUrl.set(prefs.local_llm_base_url || '');
                if (provider === 'custom') {
                    this.apiKey.set(prefs.custom_api_key || '');
                }
                if (provider !== 'ollama') {
                    this.customModelId.set(prefs.selected_llm_model || '');
                } else {
                    // For Ollama, we usually check currentModel from service, but initial sync handles this in effect
                }
                break;
        }
    }

    // Update methods only update local state (Draft)
    updateProvider(provider: string) {
        this.selectedProvider.set(provider);
        // When provider changes, we should try to pre-fill from existing preferences if available
        const prefs = this.settingsService.chatPreferences();
        if (prefs) {
            this.syncInputsForProvider(provider, prefs);
        }
        // Force reset selected model if switching providers (unless sync found one)
        if (!this.currentModels().includes(this.selectedModel())) {
            this.selectedModel.set('');
        }
    }

    updateApiKey(key: string) {
        this.apiKey.set(key);
    }

    updateBaseUrl(url: string) {
        this.baseUrl.set(url);
    }

    updateCustomModelId(id: string) {
        this.customModelId.set(id);
    }

    updateSelectedModel(model: string) {
        this.selectedModel.set(model);
    }

    async saveSettings() {
        const provider = this.selectedProvider();
        const update: Partial<ChatPreferences> = {
            llm_provider: provider
        };

        // 1. Handle API Keys
        if (provider === 'openai') update.openai_api_key = this.apiKey();
        if (provider === 'anthropic') update.anthropic_api_key = this.apiKey();
        if (provider === 'groq') update.groq_api_key = this.apiKey();
        if (provider === 'custom') update.custom_api_key = this.apiKey();

        // 2. Handle Base URL
        if (['ollama', 'lm_studio', 'custom'].includes(provider)) {
            update.local_llm_base_url = this.baseUrl();
        }

        // 3. Handle Model Selection
        if (this.isManualModelInput()) {
            update.selected_llm_model = this.customModelId();
        } else if (provider === 'ollama') {
            // For Ollama, we must call setCurrentModel
            if (this.selectedModel()) {
                await this.settingsService.setCurrentModel(this.selectedModel());
            }
        } else {
            // For others (OpenAI, Anthropic, Groq), save to preferences
            update.selected_llm_model = this.selectedModel();
        }

        // 4. Save Persistence
        await this.settingsService.saveChatPreferences(update);
        this.closeModal();
    }
}
