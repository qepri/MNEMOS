import { Component, input, output, model } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
    selector: 'app-settings-discover-tab',
    standalone: true,
    imports: [CommonModule, FormsModule],
    templateUrl: './settings-discover-tab.component.html'
})
export class SettingsDiscoverTabComponent {
    searchQuery = model<string>('');
    isSearching = input<boolean>(false);
    searchResults = input.required<any[]>();

    onSearch = output<void>();
    onOpenGgufModal = output<string>();

    searchLibrary() {
        this.onSearch.emit();
    }

    openGgufModal(fullName: string) {
        this.onOpenGgufModal.emit(fullName);
    }
}
