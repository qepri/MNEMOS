import { Component, output, input, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-chat-input',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="p-4 bg-base-100 border-t border-base-200">
      <form (ngSubmit)="handleSubmit()" class="relative">
        <div class="join w-full shadow-sm">
          <input
            type="text"
            [ngModel]="questionText()"
            (ngModelChange)="questionText.set($event)"
            name="question"
            class="input input-bordered join-item w-full focus:outline-none"
            [placeholder]="placeholder()"
            autocomplete="off"
            [disabled]="isLoading()"
            required
          />
          <button
            type="submit"
            class="btn btn-primary join-item px-6"
            [disabled]="isLoading() || !questionText().trim()"
          >
            @if (isLoading()) {
              <span class="loading loading-spinner loading-sm"></span>
            } @else {
              <span class="hidden sm:inline">Enviar</span>
              <span>🚀</span>
            }
          </button>
        </div>
      </form>
    </div>
  `
})
export class ChatInputComponent {
  placeholder = input<string>('Escribe tu pregunta aquí...');
  isLoading = input<boolean>(false);

  submitMessage = output<string>();

  questionText = signal<string>('');

  handleSubmit() {
    const text = this.questionText();
    if (text.trim() && !this.isLoading()) {
      this.submitMessage.emit(text);
      this.questionText.set('');
    }
  }
}
