import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Collection } from '../../../core/models/collection.model';

@Component({
  selector: 'app-filter-bar',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="flex flex-wrap gap-4 items-center p-4 bg-sidebar border border-divider rounded-lg mb-4">
      <!-- Search -->
      <div class="flex items-center gap-2 flex-grow max-w-xs px-3 py-2 bg-input border border-divider rounded-lg focus-within:ring-2 focus-within:ring-accent">
        <input type="text" class="grow bg-transparent border-none focus:outline-none text-sm placeholder-secondary" placeholder="Search..." [(ngModel)]="searchText" (ngModelChange)="onSearchChange()" />
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-4 h-4 text-secondary"><path fill-rule="evenodd" d="M9.965 11.026a5 5 0 1 1 1.06-1.06l2.755 2.754a.75.75 0 1 1-1.06 1.06l-2.755-2.754ZM10.5 7a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0Z" clip-rule="evenodd" /></svg>
      </div>

      <!-- Collection Filter -->
      <select class="w-full max-w-xs px-3 py-2 bg-input border border-divider rounded-lg focus:outline-none focus:ring-2 focus:ring-accent text-sm" [(ngModel)]="selectedCollectionId" (change)="onCollectionChange()">
        <option [ngValue]="null">All Collections</option>
        <option [value]="'uncategorized'">Uncategorized</option>
        <option *ngFor="let col of collections" [value]="col.id">{{ col.name }}</option>
      </select>

      <!-- File Type Filter -->
      <select class="w-full max-w-xs px-3 py-2 bg-input border border-divider rounded-lg focus:outline-none focus:ring-2 focus:ring-accent text-sm" [(ngModel)]="selectedFileType" (change)="onTypeChange()">
        <option [ngValue]="null">All Types</option>
        <option value="pdf">PDF</option>
        <option value="epub">EPUB</option>
        <option value="audio">Audio</option>
        <option value="video">Video</option>
        <option value="youtube">YouTube</option>
      </select>
    </div>
  `
})
export class FilterBarComponent {
  @Input() collections: Collection[] = [];
  @Output() filterChange = new EventEmitter<any>();

  searchText: string = '';
  selectedCollectionId: string | null = null;
  selectedFileType: string | null = null;

  onSearchChange() {
    this.emitFilters();
  }

  onCollectionChange() {
    this.emitFilters();
  }

  onTypeChange() {
    this.emitFilters();
  }

  emitFilters() {
    this.filterChange.emit({
      search: this.searchText,
      collectionId: this.selectedCollectionId,
      fileType: this.selectedFileType
    });
  }
}
