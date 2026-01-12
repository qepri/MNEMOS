import { Injectable, signal, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ApiEndpoints } from '@core/constants/api-endpoints';
import {
  ModelsResponse,
  CurrentModelResponse,
  ChatPreferences,
  SystemPromptsResponse,
  SystemPrompt,
  LibrarySearchResponse,
  ModelPullRequest,
  ModelPullResponse,
  PullStatusResponse,
  MemoriesResponse,
  LLMConnection,
  LLMConnectionsResponse
} from '@core/models';

@Injectable({
  providedIn: 'root'
})
export class SettingsService {
  private http = inject(HttpClient);

  // State
  models = signal<ModelsResponse | null>(null);
  currentModel = signal<string | null>(null);
  currentProvider = signal<string | null>(null);
  chatPreferences = signal<ChatPreferences | null>(null);
  llmConnections = signal<LLMConnection[]>([]);
  systemPrompts = signal<SystemPrompt[]>([]);
  isLoading = signal<boolean>(false);

  async loadConnections() {
    try {
      const response = await firstValueFrom(
        this.http.get<LLMConnectionsResponse>(ApiEndpoints.SETTINGS_CONNECTIONS)
      );
      this.llmConnections.set(response.connections);
    } catch (error) {
      console.error('Failed to load connections', error);
    }
  }

  async createConnection(connection: Partial<LLMConnection>): Promise<LLMConnection> {
    try {
      const newConn = await firstValueFrom(
        this.http.post<LLMConnection>(ApiEndpoints.SETTINGS_CONNECTIONS, connection)
      );
      this.llmConnections.update(conns => [newConn, ...conns]);
      return newConn;
    } catch (error) {
      console.error('Failed to create connection', error);
      throw error;
    }
  }

  async updateConnection(id: string, connection: Partial<LLMConnection>): Promise<LLMConnection> {
    try {
      const updatedConn = await firstValueFrom(
        this.http.put<LLMConnection>(`${ApiEndpoints.SETTINGS_CONNECTIONS}/${id}`, connection)
      );
      this.llmConnections.update(conns => conns.map(c => c.id === id ? updatedConn : c));
      return updatedConn;
    } catch (error) {
      console.error('Failed to update connection', error);
      throw error;
    }
  }

  async deleteConnection(id: string) {
    try {
      await firstValueFrom(
        this.http.delete(ApiEndpoints.SETTINGS_CONNECTION_DELETE(id))
      );
      this.llmConnections.update(conns => conns.filter(c => c.id !== id));
    } catch (error) {
      console.error('Failed to delete connection', error);
      throw error;
    }
  }

  async setActiveConnection(id: string | null) {
    try {
      await firstValueFrom(
        this.http.post(ApiEndpoints.SETTINGS_CONNECTION_ACTIVE, { connection_id: id })
      );
      // Refresh prefs to verify state (optional but good practice)
      await this.loadChatPreferences();
    } catch (error) {
      console.error('Failed to set active connection', error);
      throw error;
    }
  }

  async loadModels() {
    this.isLoading.set(true);

    try {
      const models = await firstValueFrom(
        this.http.get<ModelsResponse>(ApiEndpoints.SETTINGS_MODELS)
      );
      this.models.set(models);
    } catch (error) {
      console.error('Failed to load models', error);
    } finally {
      this.isLoading.set(false);
    }
  }

  async loadCurrentModel() {
    try {
      const response = await firstValueFrom(
        this.http.get<CurrentModelResponse>(ApiEndpoints.SETTINGS_CURRENT_MODEL)
      );
      this.currentModel.set(response.model);
      this.currentProvider.set(response.provider);
    } catch (error) {
      console.error('Failed to load current model', error);
    }
  }

  async setCurrentModel(modelName: string) {
    try {
      await firstValueFrom(
        this.http.post(ApiEndpoints.SETTINGS_CURRENT_MODEL, { model: modelName })
      );
      this.currentModel.set(modelName);
    } catch (error) {
      console.error('Failed to set current model', error);
      throw error;
    }
  }

  async deleteModel(modelName: string) {
    try {
      await firstValueFrom(
        this.http.delete(ApiEndpoints.SETTINGS_MODELS, {
          body: { model: modelName }
        })
      );
      await this.loadModels();
    } catch (error) {
      console.error('Failed to delete model', error);
      throw error;
    }
  }

  async loadChatPreferences() {
    try {
      const prefs = await firstValueFrom(
        this.http.get<ChatPreferences>(ApiEndpoints.SETTINGS_CHAT)
      );
      this.chatPreferences.set(prefs);
    } catch (error) {
      console.error('Failed to load chat preferences', error);
    }
  }

  async saveChatPreferences(prefs: Partial<ChatPreferences>) {
    try {
      await firstValueFrom(
        this.http.post(ApiEndpoints.SETTINGS_CHAT, prefs)
      );
      await this.loadChatPreferences();
    } catch (error) {
      console.error('Failed to save chat preferences', error);
      throw error;
    }
  }

  async loadSystemPrompts() {
    try {
      const response = await firstValueFrom(
        this.http.get<SystemPromptsResponse>(ApiEndpoints.SETTINGS_PROMPTS)
      );
      this.systemPrompts.set(response.prompts);
    } catch (error) {
      console.error('Failed to load system prompts', error);
    }
  }

  async createSystemPrompt(title: string, content: string): Promise<SystemPrompt> {
    try {
      const prompt = await firstValueFrom(
        this.http.post<SystemPrompt>(ApiEndpoints.SETTINGS_PROMPTS, { title, content })
      );
      this.systemPrompts.update(prompts => [...prompts, prompt]);
      return prompt;
    } catch (error) {
      console.error('Failed to create system prompt', error);
      throw error;
    }
  }

  async updateSystemPrompt(id: string, data: Partial<SystemPrompt>) {
    try {
      const updated = await firstValueFrom(
        this.http.put<SystemPrompt>(ApiEndpoints.SETTINGS_PROMPT_UPDATE(id), data)
      );
      this.systemPrompts.update(prompts =>
        prompts.map(p => p.id === id ? updated : p)
      );
    } catch (error) {
      console.error('Failed to update system prompt', error);
      throw error;
    }
  }

  async deleteSystemPrompt(id: string) {
    try {
      await firstValueFrom(
        this.http.delete(ApiEndpoints.SETTINGS_PROMPT_DELETE(id))
      );
      this.systemPrompts.update(prompts => prompts.filter(p => p.id !== id));
    } catch (error) {
      console.error('Failed to delete system prompt', error);
      throw error;
    }
  }

  async searchLibrary(query?: string, sort: string = 'downloads', limit: number = 30): Promise<LibrarySearchResponse> {
    try {
      let params = new HttpParams()
        .set('sort', sort)
        .set('limit', limit.toString());

      if (query) {
        params = params.set('q', query);
      }

      return await firstValueFrom(
        this.http.get<LibrarySearchResponse>(ApiEndpoints.SETTINGS_LIBRARY_SEARCH, { params })
      );
    } catch (error) {
      console.error('Failed to search library', error);
      throw error;
    }
  }

  async pullModel(request: ModelPullRequest): Promise<ModelPullResponse> {
    try {
      return await firstValueFrom(
        this.http.post<ModelPullResponse>(ApiEndpoints.SETTINGS_PULL, request)
      );
    } catch (error) {
      console.error('Failed to pull model', error);
      throw error;
    }
  }

  async scanImports(): Promise<string[]> {
    try {
      const response = await firstValueFrom(
        this.http.get<{ files: string[] }>('/api/settings/import/scan')
      );
      return response.files;
    } catch (error) {
      console.error('Failed to scan imports', error);
      return [];
    }
  }

  async importModel(filename: string, modelName: string) {
    try {
      // This endpoint streams the response, but for simplicity in this frontend
      // we'll just wait for it or handle it as a regular request for now.
      // In a real app, we might want to handle the stream or use a different approach.
      // For now, let's assume it completes or we just trigger it.
      await firstValueFrom(
        this.http.post('/api/settings/import', { filename, model_name: modelName })
      );
      await this.loadModels();
    } catch (error) {
      console.error('Failed to import model', error);
      throw error;
    }
  }

  async getOllamaStatus(): Promise<{ status: string; id?: string }> {
    try {
      return await firstValueFrom(
        this.http.get<{ status: string; id?: string }>(ApiEndpoints.SETTINGS_OLLAMA_STATUS)
      );
    } catch (error) {
      console.error('Failed to get Ollama status', error);
      return { status: 'error' };
    }
  }

  // Returns an observable for streaming progress
  installOllamaService() {
    return this.http.post(ApiEndpoints.SETTINGS_OLLAMA_INSTALL, {}, {
      responseType: 'text',
      observe: 'events',
      reportProgress: true
    });
  }

  async startOllamaService(): Promise<{ status: string; id?: string }> {
    try {
      return await firstValueFrom(
        this.http.post<{ status: string; id?: string }>(ApiEndpoints.SETTINGS_OLLAMA_START, {})
      );
    } catch (error) {
      console.error('Failed to start Ollama service', error);
      throw error;
    }
  }

  async getPullStatus(taskId: string): Promise<PullStatusResponse> {
    try {
      return await firstValueFrom(
        this.http.get<PullStatusResponse>(ApiEndpoints.SETTINGS_PULL_STATUS(taskId))
      );
    } catch (error) {
      console.error('Failed to get pull status', error);
      throw error;
    }
  }

  async getActivePulls(): Promise<any[]> {
    try {
      return await firstValueFrom(
        this.http.get<any[]>(ApiEndpoints.SETTINGS_PULL_ACTIVE)
      );
    } catch (error) {
      console.error('Failed to get active pulls', error);
      return [];
    }
  }

  async deletePull(taskId: string): Promise<void> {
    try {
      await firstValueFrom(
        this.http.delete(ApiEndpoints.SETTINGS_PULL_DELETE(taskId))
      );
    } catch (error) {
      console.error('Failed to delete pull task', error);
      throw error;
    }
  }
  async lookupModels(provider: string, apiKey: string): Promise<any[]> {
    try {
      const response = await firstValueFrom(
        this.http.post<{ models: any[] }>('/api/settings/models/lookup', { provider, api_key: apiKey })
      );
      return response.models;
    } catch (error) {
      console.error('Failed to lookup models', error);
      throw error;
    }
  }

  async listRepoFiles(repoId: string): Promise<{ filename: string, size_mb: number, quantization: string }[]> {
    try {
      const response = await firstValueFrom(
        this.http.get<{ files: any[] }>(ApiEndpoints.SETTINGS_FILES(repoId))
      );
      return response.files;
    } catch (error) {
      console.error('Failed to list repo files', error);
      throw error;
    }
  }

  async pullModelGguf(repoId: string, filename: string, modelName: string): Promise<ModelPullResponse> {
    try {
      return await firstValueFrom(
        this.http.post<ModelPullResponse>(ApiEndpoints.SETTINGS_PULL_GGUF, {
          repo_id: repoId,
          filename: filename,
          model_name: modelName
        })
      );
    } catch (error) {
      console.error('Failed to pull GGUF model', error);
      throw error;
    }
  }

  async getActiveDownloads(): Promise<{ tasks: any[] }> {
    try {
      return await firstValueFrom(
        this.http.get<{ tasks: any[] }>(ApiEndpoints.SETTINGS_DOWNLOADS)
      );
    } catch (error) {
      console.error('Failed to get active downloads', error);
      return { tasks: [] };
    }
  }

  async getHardwareInfo(): Promise<{ ram_total: number, ram_available: number, vram_total: number, vram_available: number, gpu_name: string | null }> {
    try {
      return await firstValueFrom(
        this.http.get<any>(ApiEndpoints.SETTINGS_HARDWARE)
      );
    } catch (error) {
      console.error('Failed to get hardware info', error);
      // Return zeroes if failed
      return { ram_total: 0, ram_available: 0, vram_total: 0, vram_available: 0, gpu_name: null };
    }
  }


  // Memories
  memories = signal<MemoriesResponse | null>(null);

  async loadMemories() {
    try {
      const res = await firstValueFrom(
        this.http.get<MemoriesResponse>(ApiEndpoints.MEMORY_GET)
      );
      this.memories.set(res);
    } catch (error) {
      console.error('Failed to load memories', error);
    }
  }

  async deleteMemory(id: string) {
    try {
      await firstValueFrom(
        this.http.delete(ApiEndpoints.MEMORY_DELETE(id))
      );
      await this.loadMemories();
    } catch (error) {
      console.error('Failed to delete memory', error);
      throw error;
    }
  }
}
