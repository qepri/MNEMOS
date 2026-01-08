import { Component, computed, inject, signal, effect, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SettingsService } from '@services/settings.service';
import { ChatPreferences } from '@core/models';

@Component({
    selector: 'app-llm-selector',
    standalone: true,
    imports: [CommonModule, FormsModule],
    template: `
    <div class="space-y-4">
      <!-- Provider Selection -->
      <div class="form-control">
        <label class="label">
          <span class="label-text font-medium text-secondary">Provider</span>
        </label>
        <select 
          [ngModel]="selectedProvider()" 
          (ngModelChange)="updateProvider($event)"
          class="select select-bordered w-full bg-input border-divider text-primary focus:border-accent focus:ring-1 focus:ring-accent transition-all">
          <option value="ollama">Ollama (Local)</option>
          <option value="openai">OpenAI</option>
          <option value="anthropic">Anthropic</option>
          <option value="groq">Groq</option>
          <option value="lm_studio">LM Studio</option>
          <option value="custom">Custom (OpenAI Compatible)</option>
        </select>
      </div>

      <!-- Provider Specific Config -->

      <!-- API Key (OpenAI, Anthropic, Groq, Custom) -->
      @if (isApiKeyRequired() || selectedProvider() === 'custom') {
        <div class="form-control anime-fade-in">
          <label class="label">
            <span class="label-text font-medium text-secondary">
              {{ selectedProvider() | titlecase }} API Key
            </span>
          </label>
          <input 
            type="password" 
            [ngModel]="apiKey()"
            (ngModelChange)="updateApiKey($event)"
            placeholder="sk-..." 
            class="input input-bordered w-full bg-input border-divider text-primary focus:border-accent focus:ring-1 focus:ring-accent transition-all pl-10">
          
          @if (selectedProvider() === 'groq') {
            <div class="label">
              <span class="label-text-alt text-secondary">Get your key at <a href="https://console.groq.com" target="_blank" class="link link-accent">console.groq.com</a></span>
            </div>
          }
        </div>
      }

      <!-- Base URL (Ollama, LM Studio, Custom) -->
      @if (['ollama', 'lm_studio', 'custom'].includes(selectedProvider())) {
        <div class="form-control anime-fade-in">
          <label class="label">
            <span class="label-text font-medium text-secondary">Base URL</span>
          </label>
          <input 
            type="text" 
            [ngModel]="baseUrl()" 
            (ngModelChange)="baseUrl.set($event)"
            [placeholder]="selectedProvider() === 'ollama' ? 'http://localhost:11434' : 'http://localhost:1234/v1'"
            class="input input-bordered w-full bg-input border-divider text-primary focus:border-accent focus:ring-1 focus:ring-accent transition-all">
        </div>
      }

      <!-- Model Selection (Dropdown) -->
      @if (!isManualModelInput()) {
        <div class="form-control anime-fade-in">
          <label class="label">
            <span class="label-text font-medium text-secondary">Available Models</span>
          </label>
          <select 
            [ngModel]="selectedModel()" 
            (ngModelChange)="selectedModel.set($event)"
            class="select select-bordered w-full bg-input border-divider text-primary focus:border-accent focus:ring-1 focus:ring-accent transition-all"
            [disabled]="currentModels().length === 0">
            <option value="" disabled selected>Select a model</option>
            @for (model of currentModels(); track model.name) {
              <option [value]="model.name">
                {{ model.name }} {{ model.vision ? '(Vision)' : '' }}
              </option>
            }
          </select>
          @if (currentModels().length === 0) {
            <div class="label">
              <span class="label-text-alt text-error">No models found. Check connection/key.</span>
            </div>
          }
        </div>
      }

      <!-- Manual Model ID (LM Studio, Custom) -->
      @if (isManualModelInput()) {
        <div class="form-control anime-fade-in">
          <label class="label">
            <span class="label-text font-medium text-secondary">Model ID</span>
          </label>
          <input 
            type="text" 
            [ngModel]="customModelId()" 
            (ngModelChange)="customModelId.set($event)"
            placeholder="e.g., local-model" 
            class="input input-bordered w-full bg-input border-divider text-primary focus:border-accent focus:ring-1 focus:ring-accent transition-all">
        </div>
      }
    </div>
  `,
    styles: [`
    .anime-fade-in {
      animation: fadeIn 0.3s ease-out forwards;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(-5px); }
      to { opacity: 1; transform: translateY(0); }
    }
  `]
})
export class LlmSelectorComponent {
    settingsService = inject(SettingsService);

    // Inputs: Allow initializing with preferences
    preferences = input<ChatPreferences | null>(null);

    // Internal State
    selectedProvider = signal<string>('ollama');
    apiKey = signal<string>('');
    baseUrl = signal<string>('');
    customModelId = signal<string>('');
    selectedModel = signal<string>('');

    fetchedGroqModels = signal<any[]>([]);

    // Hardcoded Model Lists (same as before)
    readonly openaiModels = [
        { name: 'gpt-4o', vision: true },
        { name: 'gpt-4o-mini', vision: true },
        { name: 'gpt-4.5-preview', vision: true },
        { name: 'o1-preview', vision: false },
        { name: 'o1-mini', vision: false }
    ];
    readonly anthropicModels = [
        { name: 'claude-3-5-sonnet-latest', vision: true },
        { name: 'claude-3-5-haiku-latest', vision: true },
        { name: 'claude-3-opus-latest', vision: true }
    ];
    readonly groqModels = [
        { name: 'deepseek-r1-distill-llama-70b', vision: false },
        { name: 'gemma-7b-it', vision: false },
        { name: 'gemma2-9b-it', vision: false },
        { name: 'llama-3.1-70b-versatile', vision: false },
        { name: 'llama-3.1-8b-instant', vision: false },
        { name: 'llama-3.2-11b-vision-preview', vision: true },
        { name: 'llama-3.2-90b-vision-preview', vision: true },
        { name: 'llama-3.3-70b-versatile', vision: false },
        { name: 'llama3-70b-8192', vision: false },
        { name: 'llama3-8b-8192', vision: false },
        { name: 'openai/gpt-oss-120b', vision: false },
        { name: 'openai/gpt-oss-20b', vision: false }
    ];


    constructor() {
        // Sync when preferences input changes
        effect(() => {
            const prefs = this.preferences();
            if (prefs) {
                this.selectedProvider.set(prefs.llm_provider || 'ollama');
                this.initFromPrefs(prefs.llm_provider || 'ollama', prefs);
            }
        }, { allowSignalWrites: true });
    }

    initFromPrefs(provider: string, prefs: ChatPreferences) {
        this.apiKey.set('');
        this.baseUrl.set('');
        this.customModelId.set('');

        // Set model
        if (provider === 'ollama') {
            this.selectedModel.set(this.settingsService.currentModel() || '');
        } else {
            this.selectedModel.set(prefs.selected_llm_model || '');
        }

        switch (provider) {
            case 'openai':
                this.apiKey.set(prefs.openai_api_key || '');
                break;
            case 'anthropic':
                this.apiKey.set(prefs.anthropic_api_key || '');
                break;
            case 'groq':
                this.apiKey.set(prefs.groq_api_key || '');
                if (prefs.groq_api_key) this.loadGroqModels(prefs.groq_api_key);
                break;
            case 'lm_studio':
            case 'custom':
            case 'ollama':
                this.baseUrl.set(prefs.local_llm_base_url || '');
                if (provider === 'custom') this.apiKey.set(prefs.custom_api_key || '');
                if (provider !== 'ollama') this.customModelId.set(prefs.selected_llm_model || '');
                break;
        }
    }

    // Computed
    isApiKeyRequired = computed(() => ['openai', 'anthropic', 'groq'].includes(this.selectedProvider()));
    isManualModelInput = computed(() => ['lm_studio', 'custom'].includes(this.selectedProvider()));

    currentModels = computed(() => {
        let models: any[] = [];
        switch (this.selectedProvider()) {
            case 'ollama':
                models = this.settingsService.models()?.models.map(m => ({ name: m.name, vision: !!m.vision })) || [];
                break;
            case 'openai':
                models = this.openaiModels;
                break;
            case 'anthropic':
                models = this.anthropicModels;
                break;
            case 'groq':
                models = this.fetchedGroqModels().length > 0 ? this.fetchedGroqModels() : this.groqModels;
                break;
        }
        // Alphabetical sort (case-insensitive)
        return models.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
    });

    // Actions
    updateProvider(provider: string) {
        this.selectedProvider.set(provider);
        const prefs = this.settingsService.chatPreferences();
        if (prefs) this.initFromPrefs(provider, prefs); // Try to sync existing prefs for this provider

        // Reset model if invalid
        if (!this.currentModels().some(m => m.name === this.selectedModel())) {
            this.selectedModel.set('');
        }
    }

    updateApiKey(key: string) {
        this.apiKey.set(key);
        if (this.selectedProvider() === 'groq' && key.startsWith('gsk_')) {
            this.loadGroqModels(key);
        }
    }

    async loadGroqModels(key: string) {
        try {
            const models = await this.settingsService.lookupModels('groq', key);
            this.fetchedGroqModels.set(models);
        } catch (e) { console.error(e); }
    }

    // Helper to get current state (for parent to save)
    getSnapshot(): Partial<ChatPreferences> & { ollamaModel?: string } {
        const provider = this.selectedProvider();
        const update: any = { llm_provider: provider };

        if (provider === 'openai') update.openai_api_key = this.apiKey();
        if (provider === 'anthropic') update.anthropic_api_key = this.apiKey();
        if (provider === 'groq') update.groq_api_key = this.apiKey();
        if (provider === 'custom') update.custom_api_key = this.apiKey();

        if (['ollama', 'lm_studio', 'custom'].includes(provider)) {
            update.local_llm_base_url = this.baseUrl();
        }

        if (this.isManualModelInput()) {
            update.selected_llm_model = this.customModelId();
        } else if (provider === 'ollama') {
            update.ollamaModel = this.selectedModel(); // Special handling for Ollama
        } else {
            update.selected_llm_model = this.selectedModel();
        }
        return update;
    }
}
