import { Component, EventEmitter, Output, signal, inject, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ModalService } from '../../../../services/modal.service';
import { SettingsService } from '@services/settings.service';
import { LlmSelectionModalComponent } from '../../../../components/modals';

@Component({
  selector: 'app-chat-input',
  standalone: true,
  imports: [CommonModule, FormsModule, LlmSelectionModalComponent],
  templateUrl: './chat-input.component.html',
  styleUrl: './chat-input.component.css'
})
export class ChatInputComponent {
  @Output() onSubmit = new EventEmitter<string>();

  message = signal('');
  modalService = inject(ModalService);
  settingsService = inject(SettingsService);

  isLlmModalOpen = signal<boolean>(false);

  currentModelDisplay = computed(() => {
    const prefs = this.settingsService.chatPreferences();
    const currentProvider = prefs?.llm_provider || 'ollama';

    if (currentProvider === 'ollama') {
      return this.settingsService.currentModel() || 'Select Model';
    } else {
      return prefs?.selected_llm_model || 'Select Model';
    }
  });

  onEnter(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  send() {
    if (this.message().trim()) {
      this.onSubmit.emit(this.message());
      this.message.set('');
    }
  }

  openModelSelection() {
    this.isLlmModalOpen.set(true);
  }
}
