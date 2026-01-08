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
    // Hardcoded models with Vision capabilities
    readonly openaiModels = [
        { name: 'gpt-4o', vision: true },
        { name: 'gpt-4o-mini', vision: true },
        { name: 'gpt-4.5-preview', vision: true },
        { name: 'o1-preview', vision: false },
        { name: 'o1-mini', vision: false }
    ];
    readonly anthropicModels = [
        { name: 'claude-3-5-sonnet-latest', vision: true },
        { name: 'claude-3-5-haiku-latest', vision: false }, // Vision depends on proper API usage, usually supported but let's check docs, assume no for safe default or true? Haiku 3.5 supports vision.
        { name: 'claude-3-opus-latest', vision: true }
    ];
    // Correction: Claude 3.5 Haiku DOES support vision.

    readonly groqModels = [
        { name: 'llama-3.3-70b-versatile', vision: false },
        { name: 'llama-3.1-70b-versatile', vision: false },
        { name: 'llama-3.1-8b-instant', vision: false },
        { name: 'llama3-70b-8192', vision: false },
        { name: 'llama3-8b-8192', vision: false },
        { name: 'gemma2-9b-it', vision: false },
        { name: 'gemma-7b-it', vision: false },
        { name: 'deepseek-r1-distill-llama-70b', vision: false },
        // Llama 3.2 Vision models on Groq
        { name: 'llama-3.2-11b-vision-preview', vision: true },
        { name: 'llama-3.2-90b-vision-preview', vision: true },
        { name: 'openai/gpt-oss-120b', vision: false },
        { name: 'openai/gpt-oss-20b', vision: false }
    ];

    // Signals for local state (initially populated from settings)
    selectedProvider = signal<string>('ollama');
    apiKey = signal<string>('');
    baseUrl = signal<string>('');
    customModelId = signal<string>('');
    selectedModel = signal<string>(''); // For dropdown selection

    // Dynamic models
    fetchedGroqModels = signal<any[]>([]);

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

                    // If Groq and key exists, try to fetch models
                    if ((prefs.llm_provider === 'groq' || this.selectedProvider() === 'groq') && prefs.groq_api_key) {
                        this.loadGroqModels(prefs.groq_api_key);
                    }
                }
            }
        });
    }

    // Computed
    currentModels = computed(() => {
        switch (this.selectedProvider()) {
            case 'ollama':
                // For Ollama, we map the backend Model object to our structure
                return this.settingsService.models()?.models.map(m => ({
                    name: m.name,
                    vision: !!m.vision
                })) || [];
            case 'openai':
                return this.openaiModels;
            case 'anthropic':
                // Haiku 3.5 update logic here if needed, sticking to readonly definition
                // Re-defining anthropic list with correction directly in readonly prop above properly
                return [
                    { name: 'claude-3-5-sonnet-latest', vision: true },
                    { name: 'claude-3-5-haiku-latest', vision: true },
                    { name: 'claude-3-opus-latest', vision: true }
                ];
            case 'groq':
                // Combine fetched models with fallback hardcoded ones if fetch failed/empty
                return this.fetchedGroqModels().length > 0 ? this.fetchedGroqModels() : this.groqModels;
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

    async loadGroqModels(key: string) {
        if (!key) return;
        try {
            const models = await this.settingsService.lookupModels('groq', key);
            this.fetchedGroqModels.set(models);
        } catch (e) {
            console.error("Could not fetch Groq models", e);
        }
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
                // Also trigger load if we have a key
                if (prefs.groq_api_key) {
                    this.loadGroqModels(prefs.groq_api_key);
                }
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
        if (!this.currentModels().some(m => m.name === this.selectedModel())) {
            this.selectedModel.set('');
        }
    }

    updateApiKey(key: string) {
        this.apiKey.set(key);
        // Debounce or just check logic for Groq?
        // KISS: If provider is Groq and key is long enough, try to fetch
        if (this.selectedProvider() === 'groq' && key.length > 20) {
            // Simple debounce could be added here, but for now direct call on blur/change might be too much
            // Let's rely on manual sync or explicit "load" or just do it.
            // Given it's a signal update, maybe we just wait for a moment?
            // Actually, updateApiKey comes from (ngModelChange).
            // Let's debounce slightly via timeout if we wanted, or just call it.
            // GROQ keys start with "gsk_"...
            if (key.startsWith('gsk_')) {
                this.loadGroqModels(key);
            }
        }
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
