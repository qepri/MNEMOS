import { Component, computed, inject, signal, effect, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SettingsService } from '@services/settings.service';
import { ChatPreferences, LLMConnection } from '@core/models';
import { ToastrService } from 'ngx-toastr';

@Component({
  selector: 'app-llm-selector',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './llm-selector.component.html',
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
  toastr = inject(ToastrService);

  // Inputs: Allow initializing with preferences
  preferences = input<ChatPreferences | null>(null);

  // Internal State
  selectedProvider = signal<string>('ollama');
  apiKey = signal<string>('');
  baseUrl = signal<string>('');
  customModelId = signal<string>('');
  selectedModel = signal<string>('');

  // Custom Connection State
  selectedConnectionId = signal<string>('new');
  isEditingConnection = signal<boolean>(false);

  // Form State (New & Edit)
  connForm = {
    name: signal(''),
    baseUrl: signal(''),
    apiKey: signal(''),
    defaultModel: signal(''),
    models: signal<string[]>([])
  };

  // Active Connection Computed
  activeConnection = computed(() =>
    this.settingsService.llmConnections().find((c: LLMConnection) => c.id === this.selectedConnectionId())
  );

  fetchedGroqModels = signal<any[]>([]);

  // Hardcoded Model Lists (unchanged)
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
    this.settingsService.loadConnections();

    // Sync when preferences input changes
    effect(() => {
      const prefs = this.preferences();
      if (prefs) {
        this.selectedProvider.set(prefs.llm_provider || 'ollama');
        this.initFromPrefs(prefs.llm_provider || 'ollama', prefs);

        if (prefs.active_connection_id) {
          this.selectedConnectionId.set(prefs.active_connection_id);
        } else if (prefs.llm_provider === 'custom') {
          if (this.settingsService.llmConnections().length > 0) {
            this.selectedConnectionId.set(this.settingsService.llmConnections()[0].id);
          } else {
            this.selectedConnectionId.set('new');
          }
        }
      }
    }, { allowSignalWrites: true });

    // Sync Form with Selection
    effect(() => {
      const id = this.selectedConnectionId();
      const connections = this.settingsService.llmConnections(); // Track dependency

      if (id === 'new') {
        this.resetForm();
      } else {
        const conn = connections.find(c => c.id === id);
        if (conn) {
          this.populateForm(conn);
        }
      }
    }, { allowSignalWrites: true });
  }

  initFromPrefs(provider: string, prefs: ChatPreferences) {
    this.apiKey.set('');
    this.baseUrl.set('');
    this.customModelId.set('');

    // Set model
    if (provider === 'ollama') {
      this.selectedModel.set(prefs.selected_llm_model || this.settingsService.currentModel() || '');
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
        if (provider !== 'ollama') this.customModelId.set(prefs.selected_llm_model || '');
        break;
    }
  }

  // Computed
  isApiKeyRequired = computed(() => ['openai', 'anthropic', 'groq'].includes(this.selectedProvider()));
  isManualModelInput = computed(() => ['lm_studio'].includes(this.selectedProvider()));

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
      case 'custom':
        // Custom models from active connection
        const active = this.activeConnection();
        if (active && active.models && active.models.length > 0) {
          models = active.models.map(m => ({ name: m, vision: false }));
        } else if (active && active.default_model) {
          models = [{ name: active.default_model, vision: false }];
        }
        break;
    }
    // Alphabetical sort (case-insensitive)
    return models.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
  });

  // Actions
  updateProvider(provider: string) {
    this.selectedProvider.set(provider);
    const prefs = this.settingsService.chatPreferences();
    if (prefs) this.initFromPrefs(provider, prefs);

    if (provider === 'custom') {
      this.settingsService.loadConnections();
      if (prefs?.active_connection_id) {
        this.selectedConnectionId.set(prefs.active_connection_id);
      } else if (this.settingsService.llmConnections().length > 0) {
        this.selectedConnectionId.set(this.settingsService.llmConnections()[0].id);
      } else {
        this.selectedConnectionId.set('new');
      }
    }

    if (provider !== 'custom' && !this.currentModels().some(m => m.name === this.selectedModel())) {
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

  // Custom Connection Logic
  async updateConnectionSelection(connId: string) {
    this.selectedConnectionId.set(connId);

    if (connId === 'new') {
      this.resetForm();
    } else {
      // Auto-populate form for editing/viewing
      const conn = this.settingsService.llmConnections().find(c => c.id === connId);
      if (conn) {
        this.populateForm(conn);
      }
    }
  }

  populateForm(conn: LLMConnection) {
    this.connForm.name.set(conn.name);
    this.connForm.baseUrl.set(conn.base_url);
    this.connForm.apiKey.set(conn.api_key || '');
    this.connForm.defaultModel.set(conn.default_model || '');
    this.connForm.models.set(conn.models || []);
  }

  // Removed startEditing/cancelEditing as we are always in "edit/view" mode

  resetForm() {
    this.connForm.name.set('');
    this.connForm.baseUrl.set('');
    this.connForm.apiKey.set('');
    this.connForm.defaultModel.set('');
    this.connForm.models.set([]);
  }

  addModelToForm(modelInput: HTMLInputElement) {
    const val = modelInput.value.trim();
    if (val && !this.connForm.models().includes(val)) {
      this.connForm.models.update(m => [...m, val]);
      // If no default, set this as default
      if (!this.connForm.defaultModel()) {
        this.connForm.defaultModel.set(val);
      }
      modelInput.value = '';
    }
  }

  removeModelFromForm(model: string) {
    this.connForm.models.update(m => m.filter(x => x !== model));
    if (this.connForm.defaultModel() === model) {
      this.connForm.defaultModel.set(this.connForm.models()[0] || '');
    }
  }

  setDefaultModel(model: string) {
    this.connForm.defaultModel.set(model);
  }

  async saveConnection() {
    try {
      const id = this.selectedConnectionId();
      const payload = {
        name: this.connForm.name(),
        base_url: this.connForm.baseUrl(),
        api_key: this.connForm.apiKey(), // Send empty string if empty to allow clearing
        default_model: this.connForm.defaultModel(),
        models: this.connForm.models(),
        provider_type: 'openai'
      };

      if (id === 'new') {
        const newConn = await this.settingsService.createConnection({
          ...payload
        });
        // This sets the ID, but we also want to trigger the "selection" logic to populate form cleanly from source
        // effectively switching from "new" mode to "edit" mode of the created conn
        this.updateConnectionSelection(newConn.id);
        this.toastr.success('Connection created successfully');
      } else {
        await this.settingsService.updateConnection(id, payload);
        // Don't reset form! We are still editing this connection.
        // Optionally refresh form from source to be sure
        const updatedConn = this.settingsService.llmConnections().find(c => c.id === id);
        if (updatedConn) this.populateForm(updatedConn);
        this.toastr.success('Connection updated successfully');
      }

    } catch (e) {
      console.error("Failed to save connection", e);
      this.toastr.error('Failed to save connection');
      throw e; // Re-throw to let parent handle it
    }
  }

  async deleteSelectedConnection() {
    const id = this.selectedConnectionId();
    if (id && id !== 'new') {
      if (confirm('Are you sure you want to delete this connection?')) {
        await this.settingsService.deleteConnection(id);
        this.selectedConnectionId.set('new');
        await this.settingsService.setActiveConnection(null);
      }
    }
  }

  // Helper to get current state (for parent to save)
  getSnapshot(): Partial<ChatPreferences> & { ollamaModel?: string } {
    const provider = this.selectedProvider();
    const update: any = { llm_provider: provider };

    // Clear active connection if not custom
    if (provider !== 'custom') {
      update.active_connection_id = null; // Or handle this in service/backend? Backend handles override
    }

    if (provider === 'openai') update.openai_api_key = this.apiKey();
    if (provider === 'anthropic') update.anthropic_api_key = this.apiKey();
    if (provider === 'groq') update.groq_api_key = this.apiKey();

    if (['ollama', 'lm_studio'].includes(provider)) {
      update.local_llm_base_url = this.baseUrl();
    }

    if (provider === 'custom') {
      // We rely on active_connection_id being set via the actions immediately
      // But for redundancy we can pass it here too if the backend needed it in prefs
      update.active_connection_id = this.selectedConnectionId() === 'new' ? null : this.selectedConnectionId();
    }

    if (this.isManualModelInput()) {
      update.selected_llm_model = this.customModelId();
    } else if (provider === 'ollama') {
      update.ollamaModel = this.selectedModel(); // Special handling for Ollama
    } else if (provider === 'custom') {
      // For Custom, the "selected model" is the connection's default model
      update.selected_llm_model = this.connForm.defaultModel();
    } else {
      update.selected_llm_model = this.selectedModel();
    }
    return update;
  }
}
