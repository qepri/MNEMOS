import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Document } from '../../../../core/models/document.model';
import { Collection } from '../../../../core/models/collection.model';

@Component({
  selector: 'app-document-properties-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  template: `
    <form [formGroup]="form" (ngSubmit)="onSubmit()" class="flex flex-col gap-4">
      
      <!-- Filename -->
      <div class="form-control">
        <label class="block mb-1 text-sm font-medium text-secondary">Original Filename</label>
        <input type="text" [value]="document?.original_filename" readonly class="w-full px-3 py-2 bg-input border border-divider rounded-lg text-secondary cursor-not-allowed opacity-70" />
      </div>

      <!-- Tag/Name -->
      <div class="form-control">
        <label class="block mb-1 text-sm font-medium">Tag / Display Name</label>
        <input type="text" formControlName="tag" class="w-full px-3 py-2 bg-input border border-divider rounded-lg focus:outline-none focus:ring-2 focus:ring-accent" placeholder="Custom tag or name" />
      </div>

      <!-- Collection -->
      <div class="form-control">
        <label class="block mb-1 text-sm font-medium">Collection</label>
        <select formControlName="collection_id" class="w-full px-3 py-2 bg-input border border-divider rounded-lg focus:outline-none focus:ring-2 focus:ring-accent">
          <option [ngValue]="null">None</option>
          <option *ngFor="let col of collections" [value]="col.id">{{ col.name }}</option>
        </select>
      </div>

      <!-- Stars -->
      <div class="form-control">
        <label class="block mb-1 text-sm font-medium">Stars (0-5)</label>
        <div class="flex gap-2">
           <ng-container *ngFor="let i of [1,2,3,4,5]">
             <label class="cursor-pointer">
               <input type="radio" formControlName="stars" [value]="i" class="sr-only peer" />
               <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" 
                    [class.text-warning]="(form.get('stars')?.value || 0) >= i"
                    [class.text-divider]="(form.get('stars')?.value || 0) < i"
                    class="w-6 h-6 hover:scale-110 transition-transform peer-checked:text-warning">
                  <path fill-rule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.007 5.404.433c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.433 2.082-5.006z" clip-rule="evenodd" />
               </svg>
             </label>
           </ng-container>
           <button type="button" class="ml-2 text-xs text-secondary hover:text-error" (click)="form.patchValue({stars: 0})">Clear</button>
        </div>
      </div>

      <!-- Comment -->
      <div class="form-control">
        <label class="block mb-1 text-sm font-medium">Comment</label>
        <textarea formControlName="comment" class="w-full px-3 py-2 bg-input border border-divider rounded-lg focus:outline-none focus:ring-2 focus:ring-accent h-24" placeholder="Add a comment..."></textarea>
      </div>

      <div class="flex justify-end gap-2 mt-4">
        <button type="button" class="btn btn-secondary" (click)="onCancel.emit()">Cancel</button>
        <button type="submit" class="btn btn-primary" [disabled]="form.invalid || form.pristine">Save Changes</button>
      </div>
    </form>
  `
})
export class DocumentPropertiesFormComponent implements OnChanges {
  @Input() document: Document | null = null;
  @Input() collections: Collection[] = [];
  @Output() save = new EventEmitter<Partial<Document>>();
  @Output() onCancel = new EventEmitter<void>();

  private fb = inject(FormBuilder);

  form = this.fb.group({
    tag: [''],
    collection_id: [null as string | null],
    stars: [0, [Validators.min(0), Validators.max(5)]],
    comment: ['']
  });

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['document'] && this.document) {
      this.form.patchValue({
        tag: this.document.tag || '',
        collection_id: this.document.collection_id || null,
        stars: this.document.stars || 0,
        comment: this.document.comment || ''
      });
    }
  }

  onSubmit() {
    if (this.form.valid) {
      this.save.emit(this.form.value as Partial<Document>);
    }
  }
}
