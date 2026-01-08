import { Component, model, inject, viewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SettingsService } from '@services/settings.service';
import { LlmSelectorComponent } from '@shared/components/llm-selector/llm-selector.component';

@Component({
    selector: 'app-llm-selection-modal',
    standalone: true,
    imports: [CommonModule, FormsModule, LlmSelectorComponent],
    template: `
    @if (isVisible()) {
      <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity" (click)="closeModal()"></div>

        <!-- Modal Content -->
        <div class="relative w-full max-w-lg bg-panel rounded-2xl shadow-2xl border border-divider overflow-hidden anime-scale-in flex flex-col max-h-[90vh]">
          
          <!-- Header -->
          <div class="flex items-center justify-between p-6 border-b border-divider bg-panel/50">
            <h2 class="text-xl font-semibold text-primary">Select AI Provider</h2>
            <button (click)="closeModal()" class="btn btn-ghost btn-sm btn-circle">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>

          <!-- Body -->
          <div class="p-6 overflow-y-auto custom-scrollbar">
            <app-llm-selector 
                [preferences]="settingsService.chatPreferences()"
                #llmSelector>
            </app-llm-selector>
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-end gap-3 p-6 border-t border-divider bg-panel/50 mt-auto">
            <button (click)="closeModal()" class="btn btn-ghost text-secondary hover:text-primary">Cancel</button>
            <button (click)="saveSettings()" class="btn btn-primary shadow-lg shadow-accent/20">Save Changes</button>
          </div>

        </div>
      </div>
    }
    `,
    styles: [`
    .anime-scale-in { animation: scaleIn 0.2s ease-out forwards; }
    @keyframes scaleIn {
      from { opacity: 0; transform: scale(0.95); }
      to { opacity: 1; transform: scale(1); }
    }
    `]
})
export class LlmSelectionModalComponent {
    isVisible = model<boolean>(false);
    settingsService = inject(SettingsService);

    // Access the child component to get state
    llmSelector = viewChild(LlmSelectorComponent);

    closeModal() {
        this.isVisible.set(false);
    }

    async saveSettings() {
        const selector = this.llmSelector();
        if (!selector) return;

        const update = selector.getSnapshot();
        const { ollamaModel, ...prefs } = update;

        // Save prefs
        await this.settingsService.saveChatPreferences(prefs);

        // Set Ollama model if needed
        if (ollamaModel) {
            await this.settingsService.setCurrentModel(ollamaModel);
        }

        this.closeModal();
    }
}

