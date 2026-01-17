import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { CollectionService } from '../../services/collection.service';
import { Collection } from '../../core/models/collection.model';

@Component({
    selector: 'app-collections-page',
    standalone: true,
    imports: [CommonModule, FormsModule, ReactiveFormsModule],
    template: `
    <div class="container mx-auto p-4 max-w-4xl">
      <div class="flex justify-between items-center mb-6">
        <h1 class="text-3xl font-bold">Collections</h1>
        <button class="btn btn-primary" (click)="openCreateModal()">
          + New Collection
        </button>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div *ngFor="let col of collections()" class="bg-panel rounded-lg shadow-sm border border-divider p-4 transition-shadow hover:shadow-md">
           <div class="flex justify-between items-start mb-2">
              <h2 class="text-xl font-semibold break-all">{{ col.name }}</h2>
              <div class="dropdown dropdown-end">
                    <label tabindex="0" class="btn btn-icon btn-sm cursor-pointer">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="inline-block w-5 h-5 stroke-current"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"></path></svg>
                    </label>
                    <ul tabindex="0" class="dropdown-content z-[1] menu p-2 shadow-lg bg-panel border border-divider rounded-lg w-52">
                        <li><a class="py-2 hover:bg-hover rounded-md" (click)="openEditModal(col)">Edit</a></li>
                        <li><a class="py-2 hover:bg-hover rounded-md text-error" (click)="deleteCollection(col.id)">Delete</a></li>
                    </ul>
              </div>
           </div>
           <p class="text-secondary text-sm mb-4 min-h-[3rem]">{{ col.description || 'No description' }}</p>
           <div class="flex justify-end border-t border-divider pt-3">
             <span class="text-xs text-secondary">Created: {{ col.created_at | date:'mediumDate' }}</span>
           </div>
        </div>
      </div>

       <!-- Modal -->
       <!-- Modal -->
       <div class="modal" [class.modal-open]="isModalOpen">
          <!-- Backdrop -->
          <div class="modal-backdrop" (click)="closeModal()"></div>
          
          <div class="modal-box bg-panel border border-divider p-0 overflow-hidden">
             <!-- Header -->
             <div class="flex items-center justify-between p-4 sm:p-6 border-b border-divider bg-panel/50">
                 <h3 class="font-bold text-lg text-primary">{{ isEditing ? 'Edit Collection' : 'New Collection' }}</h3>
                 <button (click)="closeModal()" class="btn btn-ghost btn-sm btn-circle text-secondary hover:text-primary">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                 </button>
             </div>
             
             <form [formGroup]="form" (ngSubmit)="onSubmit()">
                <div class="p-4 sm:p-6 space-y-4">
                    <div class="form-control w-full">
                        <label class="block text-sm font-medium text-base-content mb-2">Name</label>
                        <input type="text" formControlName="name" class="w-full px-3 py-2 bg-input border border-divider rounded-lg focus:outline-none focus:ring-2 focus:ring-accent text-base-content placeholder-secondary/50" placeholder="e.g., Finance, Science Fiction" />
                    </div>
                    
                    <div class="form-control w-full">
                        <label class="block text-sm font-medium text-base-content mb-2">Description</label>
                        <textarea formControlName="description" class="w-full px-3 py-2 bg-input border border-divider rounded-lg focus:outline-none focus:ring-2 focus:ring-accent h-24 text-base-content placeholder-secondary/50 resize-none" placeholder="Optional description"></textarea>
                    </div>

                    <p *ngIf="errorMessage" class="text-error text-sm">{{ errorMessage }}</p>
                </div>

                <!-- Footer -->
                <div class="flex items-center justify-end gap-2 p-4 sm:p-6 border-t border-divider bg-panel/50">
                    <button type="button" class="btn btn-ghost text-secondary hover:text-primary" (click)="closeModal()">Cancel</button>
                    <button type="submit" class="btn btn-primary" [disabled]="form.invalid || isLoading">
                        <span *ngIf="isLoading" class="loading-dots mr-2"><span></span><span></span><span></span></span>
                        Save
                    </button>
                </div>
             </form>
          </div>
       </div>
    </div>
  `
})
export class CollectionsPageComponent implements OnInit {
    private colService = inject(CollectionService);
    private fb = inject(FormBuilder);

    collections = signal<Collection[]>([]);

    isModalOpen = false;
    isEditing = false;
    editingId: string | null = null;
    isLoading = false;
    errorMessage = '';

    form = this.fb.group({
        name: ['', Validators.required],
        description: ['']
    });

    ngOnInit() {
        this.loadCollections();
    }

    loadCollections() {
        this.colService.getCollections().subscribe({
            next: (cols) => this.collections.set(cols),
            error: (err) => console.error('Failed to load collections', err)
        });
    }

    openCreateModal() {
        this.isEditing = false;
        this.editingId = null;
        this.form.reset();
        this.errorMessage = '';
        this.isModalOpen = true;
    }

    openEditModal(col: Collection) {
        this.isEditing = true;
        this.editingId = col.id;
        this.form.patchValue({
            name: col.name,
            description: col.description
        });
        this.errorMessage = '';
        this.isModalOpen = true;
    }

    closeModal() {
        this.isModalOpen = false;
    }

    onSubmit() {
        if (this.form.invalid) return;

        this.isLoading = true;
        this.errorMessage = '';
        const val = this.form.value;

        const request$ = this.isEditing && this.editingId
            ? this.colService.updateCollection(this.editingId, val as any)
            : this.colService.createCollection(val as any);

        request$.subscribe({
            next: (res) => {
                this.isLoading = false;
                this.loadCollections();
                this.closeModal();
            },
            error: (err) => {
                this.isLoading = false;
                if (err.status === 409) {
                    this.errorMessage = 'A collection with this name already exists.';
                } else {
                    this.errorMessage = 'An error occurred. Please try again.';
                }
            }
        });
    }

    deleteCollection(id: string) {
        if (confirm('Are you sure? Documents in this collection will be uncategorized.')) {
            this.colService.deleteCollection(id).subscribe(() => {
                this.loadCollections();
            });
        }
    }
}
