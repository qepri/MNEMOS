import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Document } from '../../../core/models/document.model';
import { Collection } from '../../../core/models/collection.model';
import { DocumentPropertiesFormComponent } from './document-properties-form/document-properties-form.component';

@Component({
  selector: 'app-library-document-modal',
  standalone: true,
  imports: [CommonModule, DocumentPropertiesFormComponent],
  template: `
    <div class="modal" [class.modal-open]="isOpen">
      <!-- Backdrop -->
      <div class="modal-backdrop" (click)="onClose.emit()"></div>

      <div class="modal-box w-11/12 max-w-5xl h-5/6 flex flex-col bg-panel border border-divider p-0 overflow-hidden">
        
        <!-- Header -->
        <div class="flex items-center justify-between p-4 sm:p-6 border-b border-divider bg-panel/50">
           <h3 class="font-bold text-lg text-primary truncate max-w-3xl">
               {{ document?.tag || document?.original_filename || 'Document Details' }}
           </h3>
           <button (click)="onClose.emit()" class="btn btn-ghost btn-sm btn-circle text-secondary hover:text-primary">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
           </button>
        </div>
        
        <div class="flex flex-grow overflow-hidden">
          <!-- Left: Preview / Metadata View -->
          <div class="w-1/2 flex flex-col gap-4 overflow-y-auto p-4 sm:p-6 border-r border-divider custom-scrollbar">
            
            <!-- Basic Info -->
            <div class="bg-input rounded-lg divide-y divide-divider border border-divider">
              <div class="p-3 flex justify-between items-center">
                <div class="text-xs text-secondary uppercase font-semibold">Type</div>
                <div class="text-sm font-medium text-base-content">{{ document?.file_type | uppercase }}</div>
              </div>
              <div class="p-3 flex justify-between items-center">
                <div class="text-xs text-secondary uppercase font-semibold">Collection</div>
                <div class="text-sm font-medium text-base-content">{{ getCollectionName(document?.collection_id) }}</div>
              </div>
              <div class="p-3 flex justify-between items-center">
                 <div class="text-xs text-secondary uppercase font-semibold">Rating</div>
                 <div class="flex text-warning">
                    <ng-container *ngFor="let i of [1,2,3,4,5]">
                        <svg *ngIf="(document?.stars || 0) >= i" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-4 h-4">
                            <path fill-rule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.007 5.404.433c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.433 2.082-5.006z" clip-rule="evenodd" />
                        </svg>
                        <svg *ngIf="(document?.stars || 0) < i" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="w-4 h-4 text-divider">
                             <path stroke-linecap="round" stroke-linejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.563.045.79.734.37 1.144l-4.197 4.093a.562.562 0 00-.161.498l1.272 5.466c.13.56-.445.986-.889.704l-4.757-2.875a.562.562 0 00-.586 0l-4.757 2.875c-.443.282-1.018-.145-.889-.704l1.272-5.466a.562.562 0 00-.161-.498L2.43 10.43c-.42-.41-.192-1.099.37-1.144l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
                        </svg>
                    </ng-container>
                 </div>
              </div>
            </div>

            <!-- Comment -->
            <div class="bg-panel border border-divider rounded-lg p-4" *ngIf="document?.comment">
                 <h4 class="text-xs text-secondary mb-2 uppercase font-semibold">Comment</h4>
                 <p class="text-sm whitespace-pre-wrap text-base-content">{{ document?.comment }}</p>
            </div>

             <!-- JSON Metadata (Debug/Advanced) -->
             <details class="group bg-input rounded-lg border border-divider">
                <summary class="p-3 cursor-pointer text-sm font-medium flex justify-between items-center text-secondary hover:text-primary transition-colors focus:outline-none">
                    <span>Technical Metadata</span>
                    <span class="group-open:rotate-180 transition-transform">▼</span>
                </summary>
                <div class="p-3 pt-0 border-t border-divider"> 
                    <pre class="text-xs overflow-x-auto p-2 bg-base-200 rounded mt-2 text-base-content/80 font-mono">{{ document?.metadata | json }}</pre>
                </div>
            </details>
            
          </div>

          <!-- Right: Edit Form -->
          <div class="w-1/2 overflow-y-auto p-4 sm:p-6 custom-scrollbar bg-panel">
             <h4 class="font-bold mb-4 text-primary">Edit Properties</h4>
             <app-document-properties-form 
                [document]="document" 
                [collections]="collections"
                (save)="onSave.emit($event)"
                (onCancel)="onClose.emit()"
             ></app-document-properties-form>
          </div>
        </div>
      </div>
    </div>
  `
})
export class LibraryDocumentModalComponent {
  @Input() document: Document | null = null;
  @Input() collections: Collection[] = [];
  @Input() isOpen: boolean = false;
  @Output() onClose = new EventEmitter<void>();
  @Output() onSave = new EventEmitter<Partial<Document>>();

  getCollectionName(id?: string | null): string {
    if (!id) return 'Uncategorized';
    const col = this.collections.find(c => c.id === id);
    return col ? col.name : 'Unknown';
  }
}
