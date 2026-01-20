import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Document } from '../../../core/models/document.model';
import { Collection } from '../../../core/models/collection.model';
import { DocumentPropertiesFormComponent } from './document-properties-form/document-properties-form.component';

@Component({
  selector: 'app-library-document-modal',
  standalone: true,
  imports: [CommonModule, DocumentPropertiesFormComponent],
  template: `
    <!-- Main Modal Overlay -->
    <div *ngIf="isOpen" class="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6" role="dialog" aria-modal="true">
      <!-- Backdrop -->
      <div class="fixed inset-0 bg-black/80 backdrop-blur-sm transition-opacity" (click)="onClose.emit()"></div>

      <!-- Modal Panel -->
      <div class="relative w-full max-w-[95vw] h-[90vh] bg-[#14181c] rounded-2xl shadow-2xl flex flex-col overflow-hidden border border-white/10 ring-1 ring-black/5">
        
        <!-- Header -->
        <div class="flex items-center justify-between px-8 py-5 border-b border-white/10 bg-[#14181c] shrink-0">
           <div class="flex items-center gap-4 overflow-hidden">
                <!-- File Type Icon -->
                <div class="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary shrink-0 border border-primary/20">
                    <span class="text-xs font-bold uppercase tracking-wider">{{ document?.file_type?.slice(0,3) }}</span>
                </div>
                
                <div class="flex flex-col overflow-hidden">
                    <h3 class="font-bold text-2xl text-gray-100 truncate tracking-tight">
                        {{ document?.tag || document?.original_filename || 'Document Details' }}
                    </h3>
                    <div class="flex items-center gap-2 text-sm text-gray-400 font-medium">
                        <span class="truncate max-w-md">{{ document?.original_filename }}</span>
                        <span class="w-1 h-1 rounded-full bg-gray-600"></span>
                        <span>{{ document?.created_at | date:'mediumDate' }}</span>
                    </div>
                </div>
           </div>
           
           <div class="flex items-center gap-2">
               <!-- Close Button -->
               <button (click)="onClose.emit()" class="p-2 rounded-full text-gray-400 hover:text-white hover:bg-white/10 transition-colors">
                  <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                  </svg>
               </button>
           </div>
        </div>
        
        <!-- Content Grid -->
        <div class="flex-grow flex overflow-hidden relative bg-[#0f1115]">
            
            <!-- Left Column: Content & Summary (Flexible Width) -->
            <div class="flex-1 overflow-y-auto custom-scrollbar p-8">
                <div class="max-w-4xl mx-auto space-y-8">
                    
                    <!-- Summary Card -->
                    <div class="bg-[#14181c] border border-white/10 rounded-xl shadow-sm overflow-hidden group">
                        <div class="px-6 py-4 border-b border-white/5 bg-white/5 flex items-center gap-2">
                             <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="21" y1="10" x2="3" y2="10"></line><line x1="21" y1="6" x2="3" y2="6"></line><line x1="21" y1="14" x2="3" y2="14"></line><line x1="21" y1="18" x2="3" y2="18"></line></svg>
                             <h4 class="font-bold text-sm uppercase tracking-wider text-gray-400">Summary</h4>
                        </div>
                        <div class="p-8">
                            @if (document?.summary) {
                                <p class="text-lg leading-relaxed text-gray-200 font-serif whitespace-pre-line">{{ document?.summary }}</p>
                            } @else {
                                <div class="flex flex-col items-center justify-center py-12 text-gray-600 gap-3">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="w-12 h-12 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                                    <span class="italic font-medium">No summary available yet.</span>
                                </div>
                            }
                        </div>
                    </div>

                    <!-- Transcription Card -->
                    <div *ngIf="isAudioVideo()" class="bg-[#14181c] border border-white/10 rounded-xl shadow-sm overflow-hidden">
                        <div class="p-6 flex items-center justify-between">
                            <div class="flex items-center gap-5">
                                <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-secondary/20 to-secondary/5 flex items-center justify-center text-secondary ring-1 ring-inset ring-secondary/20">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg>
                                </div>
                                <div>
                                    <h4 class="font-bold text-lg text-gray-200">Transcription</h4>
                                    <p class="text-sm text-gray-500 font-medium">{{ hasTranscription() ? 'Ready to view' : 'Generate to view text' }}</p>
                                </div>
                            </div>
                            
                            <div class="flex items-center gap-3">
                                <button *ngIf="hasTranscription()" (click)="openTranscriptionModal()" class="px-4 py-2 rounded-lg border border-white/10 text-gray-300 hover:border-primary/50 hover:bg-primary/5 hover:text-primary transition-all flex items-center gap-2 font-medium text-sm">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                                    View Full Text
                                </button>
                                
                                <button *ngIf="!hasTranscription()" (click)="generateTranscription()" [disabled]="isTranscribing" class="px-5 py-2 rounded-lg bg-primary hover:bg-primary-focus text-primary-content font-medium text-sm flex items-center gap-2 transition-colors shadow-lg shadow-primary/20">
                                     <svg *ngIf="isTranscribing" class="animate-spin -ml-1 mr-1 h-4 w-4 text-primary-content" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                     </svg>
                                     {{ isTranscribing ? 'Generating...' : 'Generate Transcription' }}
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Comments Section -->
                    <div *ngIf="document?.comment" class="bg-[#14181c] border border-white/10 rounded-xl shadow-sm p-6">
                        <h4 class="text-sm font-bold uppercase tracking-wider text-gray-500 mb-3 flex items-center gap-2">
                            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                            Comment
                        </h4>
                        <p class="text-gray-300 whitespace-pre-wrap leading-relaxed">{{ document?.comment }}</p>
                    </div>

                </div>
            </div>

            <!-- Right Column: Sidebar (Fixed Width 400px) -->
            <div class="w-[400px] shrink-0 bg-[#14181c] border-l border-white/10 overflow-y-auto custom-scrollbar p-6 text-gray-300">
                 <h4 class="font-bold text-lg text-gray-200 mb-6 border-b border-white/10 pb-4">Properties</h4>
                 
                 <app-document-properties-form 
                    [document]="document" 
                    [collections]="collections"
                    (save)="onSave.emit($event)"
                    (onCancel)="onClose.emit()"
                 ></app-document-properties-form>
                 
                 <div class="h-8"></div> <!-- Spacer -->

                 <div class="border-t border-white/10 pt-6">
                     <button (click)="showTechnical = !showTechnical" class="w-full flex items-center justify-between text-sm font-bold text-gray-500 hover:text-primary transition-colors mb-2">
                        <span>Technical Metadata</span>
                        <span  [class.rotate-180]="showTechnical" class="transition-transform">▼</span>
                     </button>
                     <div *ngIf="showTechnical" class="bg-black/20 rounded-lg border border-white/5 p-3 overflow-hidden animate-fade-in">
                        <pre class="text-[10px] text-gray-400 font-mono overflow-x-auto custom-scrollbar whitespace-pre-wrap break-all">{{ document?.metadata | json }}</pre>
                     </div>
                 </div>
            </div>
            
        </div>
      </div>
    </div>

    <!-- Transcription Viewer Modal (Centered) -->
    <div *ngIf="showTranscriptionModal" class="fixed inset-0 z-[60] flex items-center justify-center p-4 sm:p-6" role="dialog" aria-modal="true">
        <!-- Backdrop -->
        <div class="fixed inset-0 bg-black/80 backdrop-blur-sm transition-opacity" (click)="closeTranscriptionModal()"></div>
        
        <!-- Modal Panel -->
        <div class="relative w-full max-w-4xl max-h-[85vh] bg-[#14181c] shadow-2xl rounded-2xl border border-white/10 flex flex-col animate-fade-in overflow-hidden ring-1 ring-black/5">
            
            <!-- Header -->
            <div class="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-[#14181c] shrink-0">
                <div class="flex items-center gap-3">
                    <h3 class="font-bold text-xl text-gray-100">Transcription</h3>
                    <span class="px-2 py-0.5 rounded-full bg-white/10 text-xs text-gray-400 font-medium">Read-only</span>
                </div>
                <div class="flex items-center gap-2">
                    <button (click)="copyTranscription()" class="px-3 py-1.5 rounded-lg text-sm font-medium text-gray-300 hover:text-white hover:bg-white/10 transition-colors flex items-center gap-2 border border-white/5">
                        <svg *ngIf="!copied" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                        <svg *ngIf="copied" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-green-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                        {{ copied ? 'Copied!' : 'Copy Text' }}
                    </button>
                    
                    <button (click)="downloadTranscription()" class="px-3 py-1.5 rounded-lg text-sm font-medium text-gray-300 hover:text-white hover:bg-white/10 transition-colors flex items-center gap-2 border border-white/5">
                        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                        Download
                    </button>
                    
                    <button (click)="closeTranscriptionModal()" class="p-2 rounded-full text-gray-400 hover:bg-white/10 hover:text-white transition-colors ml-2">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                    </button>
                </div>
            </div>

            <!-- Content -->
            <div class="flex-grow overflow-y-auto p-8 custom-scrollbar bg-[#14181c] relative min-h-[300px]">
                <div *ngIf="transcriptionText" class="prose prose-invert max-w-none">
                    <pre class="whitespace-pre-wrap font-sans text-base leading-relaxed text-gray-300 bg-transparent border-none p-0">{{ transcriptionText }}</pre>
                </div>
                
                <div *ngIf="loadingTranscription" class="absolute inset-0 flex flex-col items-center justify-center bg-[#14181c] z-10 transition-opacity">
                    <div class="loading loading-spinner loading-lg text-primary mb-4"></div>
                    <p class="text-gray-400 animate-pulse">Loading transcription...</p>
                </div>
                
                <div *ngIf="!loadingTranscription && !transcriptionText" class="absolute inset-0 flex flex-col items-center justify-center text-gray-500 gap-3">
                     <svg xmlns="http://www.w3.org/2000/svg" class="w-12 h-12 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" /></svg>
                     <p>No text content found.</p>
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

  isTranscribing = false;

  // Transcription Modal State
  showTranscriptionModal = false;
  transcriptionText: string = '';
  loadingTranscription = false;
  copied = false;

  // UI toggle
  showTechnical = false;

  constructor(private http: HttpClient) { }

  getCollectionName(id?: string | null): string {
    if (!id) return 'Uncategorized';
    const col = this.collections.find(c => c.id === id);
    return col ? col.name : 'Unknown';
  }

  isAudioVideo(): boolean {
    if (!this.document) return false;
    return ['audio', 'video', 'youtube'].includes(this.document.file_type);
  }

  hasTranscription(): boolean {
    // Check if metadata has transcription_file
    const meta = this.document?.metadata as any;
    return !!(meta && meta.transcription_file);
  }

  generateTranscription() {
    if (!this.document) return;
    this.isTranscribing = true;
    this.http.post(`/api/documents/${this.document.id}/transcribe`, {}).subscribe({
      next: (res: any) => {
        this.isTranscribing = false;
        // Update local document metadata to show download button immediately
        if (this.document) {
          const meta = this.document.metadata as any || {};
          meta.transcription_file = res.file;
          this.document = { ...this.document, metadata: meta };
        }
      },
      error: (err: any) => {
        this.isTranscribing = false;
        console.error('Transcription failed', err);
        alert('Transcription failed: ' + (err.error?.error || err.message));
      }
    });
  }

  downloadTranscription() {
    if (!this.document) return;
    // Trigger download by opening window with download query param
    window.open(`/api/documents/${this.document.id}/transcription?download=true`, '_blank');
  }

  // --- Transcription Viewer Logic ---

  openTranscriptionModal() {
    if (!this.document) return;
    this.showTranscriptionModal = true;
    this.loadTranscriptionText();
  }

  closeTranscriptionModal() {
    this.showTranscriptionModal = false;
    this.transcriptionText = ''; // Clear to save memory? or cache it?
    this.copied = false;
  }

  loadTranscriptionText() {
    if (!this.document || !this.hasTranscription()) return;

    this.loadingTranscription = true;
    // We can use the same endpoint as download but via HttpClient to get text
    // Need responseType: 'text'
    this.http.get(`/api/documents/${this.document.id}/transcription`, { responseType: 'text' }).subscribe({
      next: (text) => {
        this.transcriptionText = text;
        this.loadingTranscription = false;
      },
      error: (err) => {
        console.error('Failed to load transcription text', err);
        this.transcriptionText = "Error loading transcription content.";
        this.loadingTranscription = false;
      }
    });
  }

  copyTranscription() {
    if (!this.transcriptionText) return;

    navigator.clipboard.writeText(this.transcriptionText).then(() => {
      this.copied = true;
      setTimeout(() => this.copied = false, 2000);
    }).catch(err => {
      console.error('Failed to copy text', err);
    });
  }
}
