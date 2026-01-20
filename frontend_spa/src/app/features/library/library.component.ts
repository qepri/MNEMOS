import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DocumentsService } from '../../services/documents.service';
import { CollectionService } from '../../services/collection.service';
import { Collection } from '../../core/models/collection.model';
import { Document } from '../../core/models/document.model';
import { FilterBarComponent } from './filter-bar/filter-bar.component';
import { LibraryDocumentModalComponent } from './library-document-modal/library-document-modal.component';

@Component({
    selector: 'app-library-page',
    standalone: true,
    imports: [CommonModule, FilterBarComponent, LibraryDocumentModalComponent],
    template: `
    <div class="container mx-auto p-4 h-full flex flex-col">
      <h1 class="text-3xl font-bold mb-6">Library</h1>
      
      <!-- Filter Bar -->
      <app-filter-bar 
        [collections]="collections()" 
        (filterChange)="onFilterChange($event)">
      </app-filter-bar>

      <!-- Document Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 overflow-y-auto flex-grow content-start">
        <div *ngFor="let doc of filteredDocuments()" 
             class="bg-panel rounded-lg shadow-sm border border-divider hover:shadow-md transition-all cursor-pointer relative group p-4"
             (click)="openDocument(doc)">
          
             <div class="flex justify-between items-start mb-2">
                <span class="px-2 py-0.5 text-xs font-medium border border-divider rounded-full text-secondary">{{ doc.file_type | uppercase }}</span>
                <div *ngIf="doc.stars" class="flex text-warning">
                    <ng-container *ngFor="let i of [].constructor(doc.stars)">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-3 h-3">
                            <path fill-rule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.007 5.404.433c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.433 2.082-5.006z" clip-rule="evenodd" />
                        </svg>
                    </ng-container>
                </div>
             </div>
             
             <h2 class="text-sm font-semibold mb-2 line-clamp-2 min-h-[2.5rem]" [title]="doc.original_filename">
                {{ doc.tag || doc.original_filename }}
             </h2>
             
             <div class="flex items-center justify-between text-xs text-secondary mt-auto pt-2 border-t border-divider">
                <span>{{ doc.created_at | date:'mediumDate' }}</span>
                <span *ngIf="doc.collection_id" class="px-2 py-0.5 bg-hover rounded-full max-w-[50%] truncate">
                    {{ getCollectionName(doc.collection_id) }}
                </span>
             </div>
        </div>
        
        <!-- Empty State -->
        <div *ngIf="filteredDocuments().length === 0" class="col-span-full text-center py-10 opacity-50">
            No documents found matching filters.
        </div>
      </div>

      <!-- Modal -->
      <app-library-document-modal
        [document]="selectedDocument"
        [collections]="collections()"
        [isOpen]="!!selectedDocument"
        (onClose)="closeModal()"
        (onSave)="saveDocument($event)"
      ></app-library-document-modal>
    </div>
  `
})
export class LibraryPageComponent implements OnInit {
    private docService = inject(DocumentsService);
    private colService = inject(CollectionService);

    collections = signal<Collection[]>([]);
    documents = this.docService.documents; // Signal from service

    // Local filter state
    filterSearch = '';
    filterCollection: string | null = null; // null = all, 'uncategorized' = null in DB
    filterType: string | null = null;

    selectedDocument: Document | null = null;

    ngOnInit() {
        this.loadData();
    }

    async loadData() {
        // Load collections
        this.colService.getCollections().subscribe({
            next: (cols) => this.collections.set(cols),
            error: (err) => console.error('Failed to load collections', err)
        });

        // Load documents (initially all)
        await this.docService.fetchDocuments();
    }

    onFilterChange(filters: any) {
        this.filterSearch = filters.search.toLowerCase();
        this.filterCollection = filters.collectionId;
        this.filterType = filters.fileType;
    }

    // Computed filtering logic
    filteredDocuments() {
        return this.documents().filter(doc => {
            // Search
            const matchesSearch = !this.filterSearch ||
                (doc.original_filename && doc.original_filename.toLowerCase().includes(this.filterSearch)) ||
                (doc.tag && doc.tag.toLowerCase().includes(this.filterSearch)) ||
                (doc.comment && doc.comment.toLowerCase().includes(this.filterSearch));

            // Collection
            let matchesCollection = true;
            if (this.filterCollection === 'uncategorized') {
                matchesCollection = !doc.collection_id;
            } else if (this.filterCollection) {
                matchesCollection = doc.collection_id === this.filterCollection;
            }

            // Type
            const matchesType = !this.filterType || doc.file_type === this.filterType;

            return matchesSearch && matchesCollection && matchesType;
        });
    }

    getCollectionName(id: string): string {
        return this.collections().find(c => c.id === id)?.name || 'Unknown';
    }

    openDocument(doc: Document) {
        this.selectedDocument = doc;
    }

    closeModal() {
        this.selectedDocument = null;
    }

    async saveDocument(updates: Partial<Document>) {
        if (this.selectedDocument) {
            try {
                await this.docService.updateDocument(this.selectedDocument.id, updates);
                this.closeModal();
                // Refresh collections just in case? No need usually.
            } catch (err) {
                alert('Failed to save document');
            }
        }
    }
}
