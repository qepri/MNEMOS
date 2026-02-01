import { Component, Input, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatPreferences } from '@core/models';

interface ParamConfig {
  key: keyof ChatPreferences;
  label: string;
  description: string;
  min: number;
  max: number;
  step: number;
  default: number;
  presets?: { label: string; value: number }[];
  impact: string;
}

@Component({
  selector: 'app-llm-generation-params',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="bg-panel border border-divider rounded-xl p-4 sm:p-6">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-lg font-semibold">Generation Parameters</h2>
          <p class="text-xs text-secondary mt-1">Control LLM output quality and behavior</p>
        </div>
        <div class="flex gap-2">
          <button (click)="showHelpModal.set(true)"
            class="btn-icon text-secondary hover:text-primary" title="Help">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
          </button>
          <button (click)="resetToDefaults()"
            class="btn-secondary text-sm px-3 py-1" title="Reset to recommended defaults">
            Reset
          </button>
        </div>
      </div>

      <div class="space-y-6">
        @for (param of params; track param.key) {
          <div>
            <div class="flex items-center justify-between mb-2">
              <label class="text-sm font-medium flex items-center gap-1">
                {{ param.label }}
                <button (click)="showHelpModal.set(true)"
                  class="text-secondary hover:text-primary">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                  </svg>
                </button>
              </label>
              <div class="flex items-center gap-2">
                <input type="number" [min]="param.min" [max]="param.max" [step]="param.step"
                  [(ngModel)]="preferences[param.key]"
                  class="w-20 px-2 py-1 bg-input border border-divider rounded text-sm text-center font-mono">
                @if (param.presets) {
                  <select [(ngModel)]="preferences[param.key]"
                    class="px-2 py-1 bg-input border border-divider rounded text-xs">
                    @for (preset of param.presets; track preset.value) {
                      <option [value]="preset.value">{{ preset.label }}</option>
                    }
                  </select>
                }
              </div>
            </div>
            <input type="range" [min]="param.min" [max]="param.max" [step]="param.step"
              [(ngModel)]="preferences[param.key]"
              class="range range-accent range-sm mb-1 w-full">
            <p class="text-xs text-secondary">{{ param.description }}</p>
          </div>
        }
      </div>
    </div>

    <!-- Help Modal -->
    @if (showHelpModal()) {
      <div class="modal modal-open">
        <div class="modal-box bg-panel border border-divider rounded-2xl p-0 max-w-3xl max-h-[80vh]">
          <div class="p-4 sm:p-6 border-b border-divider sticky top-0 bg-panel z-10">
            <div class="flex items-center justify-between">
              <h3 class="text-lg font-semibold">Generation Parameters Guide</h3>
              <button (click)="showHelpModal.set(false)" class="btn-icon">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </button>
            </div>
          </div>
          <div class="p-4 sm:p-6 space-y-6 overflow-y-auto max-h-[calc(80vh-120px)]">
            @for (param of params; track param.key) {
              <div class="bg-input rounded-lg p-4 border border-divider">
                <div class="flex items-start justify-between mb-2">
                  <h4 class="font-semibold text-accent">{{ param.label }}</h4>
                  <span class="badge badge-sm badge-ghost font-mono">{{ param.default }}</span>
                </div>
                <p class="text-sm text-secondary mb-3">{{ param.description }}</p>
                <div class="grid grid-cols-2 gap-3 text-xs">
                  <div class="bg-panel rounded p-2">
                    <span class="text-secondary">Range:</span>
                    <span class="font-mono ml-2">{{ param.min }} - {{ param.max }}</span>
                  </div>
                  <div class="bg-panel rounded p-2">
                    <span class="text-secondary">Default:</span>
                    <span class="font-mono ml-2">{{ param.default }}</span>
                  </div>
                </div>
                <div class="mt-3 p-3 bg-accent-subtle rounded border-l-4 border-accent">
                  <p class="text-xs"><strong>Impact:</strong> {{ param.impact }}</p>
                </div>
              </div>
            }

            <!-- Best Practices -->
            <div class="bg-success bg-opacity-10 border border-success rounded-lg p-4">
              <h4 class="font-semibold text-success mb-2 flex items-center gap-2">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                Best Practices
              </h4>
              <ul class="text-sm space-y-2">
                <li class="flex items-start gap-2">
                  <span class="text-success mt-1">•</span>
                  <span><strong>Small models (4B):</strong> Use higher frequency_penalty (0.5+) to prevent loops</span>
                </li>
                <li class="flex items-start gap-2">
                  <span class="text-success mt-1">•</span>
                  <span><strong>Creative tasks:</strong> Increase temperature (0.8-1.0) and lower top_p (0.8-0.9)</span>
                </li>
                <li class="flex items-start gap-2">
                  <span class="text-success mt-1">•</span>
                  <span><strong>Factual tasks:</strong> Lower temperature (0.3-0.5) with default top_p</span>
                </li>
                <li class="flex items-start gap-2">
                  <span class="text-success mt-1">•</span>
                  <span><strong>Prevent repetition:</strong> Adjust frequency_penalty first, then presence_penalty</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
        <div class="modal-backdrop" (click)="showHelpModal.set(false)"></div>
      </div>
    }
  `,
  styles: [`
    :host {
      display: block;
    }
  `]
})
export class LlmGenerationParamsComponent {
  @Input({ required: true }) preferences!: ChatPreferences;

  showHelpModal = signal(false);

  params: ParamConfig[] = [
    {
      key: 'llm_max_tokens',
      label: 'Max Tokens',
      description: 'Maximum length of response. Higher = longer answers but slower.',
      min: 512,
      max: 16384,
      step: 512,
      default: 4096,
      impact: 'Prevents infinite generation. Set lower for faster responses, higher for detailed answers.',
      presets: [
        { label: 'Short', value: 1024 },
        { label: 'Medium', value: 4096 },
        { label: 'Long', value: 8192 }
      ]
    },
    {
      key: 'llm_temperature',
      label: 'Temperature',
      description: 'Randomness of output. Higher = more creative, Lower = more focused.',
      min: 0,
      max: 2,
      step: 0.1,
      default: 0.7,
      impact: 'Controls creativity vs consistency. 0.7 is balanced for most tasks.',
      presets: [
        { label: 'Precise', value: 0.3 },
        { label: 'Balanced', value: 0.7 },
        { label: 'Creative', value: 1.0 }
      ]
    },
    {
      key: 'llm_top_p',
      label: 'Top P (Nucleus Sampling)',
      description: 'Consider only tokens with top 90% probability mass. Lower = more focused.',
      min: 0.1,
      max: 1.0,
      step: 0.05,
      default: 0.9,
      impact: 'Prevents low-quality token selection. 0.9 works well with temperature.',
      presets: [
        { label: 'Strict', value: 0.7 },
        { label: 'Standard', value: 0.9 },
        { label: 'Relaxed', value: 0.95 }
      ]
    },
    {
      key: 'llm_frequency_penalty',
      label: 'Frequency Penalty',
      description: 'Penalize tokens based on repetition frequency. Higher = less repetition.',
      min: 0,
      max: 2,
      step: 0.1,
      default: 0.3,
      impact: 'CRITICAL for small models. Prevents loops. Increase if seeing repeated paragraphs.',
      presets: [
        { label: 'None', value: 0 },
        { label: 'Mild', value: 0.3 },
        { label: 'Strong', value: 0.8 }
      ]
    },
    {
      key: 'llm_presence_penalty',
      label: 'Presence Penalty',
      description: 'Penalize tokens that have appeared at all. Encourages topic diversity.',
      min: 0,
      max: 2,
      step: 0.1,
      default: 0.1,
      impact: 'Keeps responses diverse. Lower value recommended to allow coherent follow-up.',
      presets: [
        { label: 'None', value: 0 },
        { label: 'Subtle', value: 0.1 },
        { label: 'Moderate', value: 0.5 }
      ]
    }
  ];

  resetToDefaults() {
    if (!confirm('Reset all generation parameters to recommended defaults?')) return;
    this.preferences.llm_max_tokens = 4096;
    this.preferences.llm_temperature = 0.7;
    this.preferences.llm_top_p = 0.9;
    this.preferences.llm_frequency_penalty = 0.3;
    this.preferences.llm_presence_penalty = 0.1;
  }
}
