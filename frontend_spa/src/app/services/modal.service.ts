import { Injectable, signal } from '@angular/core';

@Injectable({
    providedIn: 'root'
})
export class ModalService {
    isUploadOpen = signal(false);
    isModelSelectionOpen = signal(false);

    // Upload Modal
    openUpload() {
        this.isUploadOpen.set(true);
    }

    closeUpload() {
        this.isUploadOpen.set(false);
    }

    // Model Selection Modal
    openModelSelection() {
        this.isModelSelectionOpen.set(true);
    }

    closeModelSelection() {
        this.isModelSelectionOpen.set(false);
    }
}
