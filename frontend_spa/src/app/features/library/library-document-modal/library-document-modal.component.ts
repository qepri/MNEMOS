import { Component, EventEmitter, Input, Output, inject, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Document, DocumentSection } from '../../../core/models/document.model';
import { Collection } from '../../../core/models/collection.model';
import { DocumentPropertiesFormComponent } from './document-properties-form/document-properties-form.component';
import { MarkdownDisplayComponent } from '../../../components/markdown/markdown-display.component';
import { ModalService } from '../../../services/modal.service';
import { ApiEndpoints } from '../../../core/constants/api-endpoints';
import { LlmAvailabilityService } from '@services/llm-availability.service';
import { LlmDormantComponent } from '@shared/components/llm-dormant/llm-dormant.component';

@Component({
  selector: 'app-library-document-modal',
  standalone: true,
  imports: [CommonModule, DocumentPropertiesFormComponent, MarkdownDisplayComponent, LlmDormantComponent],
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

           <div class="flex items-center gap-3">
               <!-- Open Document Button -->
               <button (click)="openDocument()" class="px-4 py-2 rounded-lg hover:bg-primary-focus text-primary-content font-medium text-sm flex items-center gap-2 transition-colors shadow-lg">
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                  {{ getActionButtonText() }}
               </button>

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
                    
                    <!-- Content Section with Tabs -->
                    <div class="space-y-4">
                        <!-- Tab Navigation -->
                        <div class="flex items-center gap-1 border-b border-white/10">
                            <button
                                (click)="activeTab = 'summary'"
                                [class.text-primary]="activeTab === 'summary'"
                                [class.border-primary]="activeTab === 'summary'"
                                [class.text-gray-500]="activeTab !== 'summary'"
                                [class.border-transparent]="activeTab !== 'summary'"
                                class="px-4 py-2 text-sm font-medium border-b-2 transition-colors hover:text-gray-300">
                                Summary
                            </button>
                            <button
                                (click)="activeTab = 'index'"
                                [class.text-primary]="activeTab === 'index'"
                                [class.border-primary]="activeTab === 'index'"
                                [class.text-gray-500]="activeTab !== 'index'"
                                [class.border-transparent]="activeTab !== 'index'"
                                class="px-4 py-2 text-sm font-medium border-b-2 transition-colors hover:text-gray-300">
                                Index
                            </button>
                            <button
                                (click)="activeTab = 'concepts'"
                                [class.text-primary]="activeTab === 'concepts'"
                                [class.border-primary]="activeTab === 'concepts'"
                                [class.text-gray-500]="activeTab !== 'concepts'"
                                [class.border-transparent]="activeTab !== 'concepts'"
                                class="px-4 py-2 text-sm font-medium border-b-2 transition-colors hover:text-gray-300">
                                Key Concepts
                            </button>
                        </div>

                        <!-- Tab Content -->
                        <div class="pt-2">
                            <!-- Summary Tab -->
                            @if (activeTab === 'summary') {
                                <div class="text-base leading-relaxed text-gray-200">
                                    @if (document?.summary) {
                                        <app-markdown-display [content]="document!.summary!"></app-markdown-display>
                                    } @else if (!llmAvailability.isAvailable()) {
                                        <!-- Without a model, "Generate Manual Summary" is a
                                             button that can only fail. Explain instead. -->
                                        <app-llm-dormant heading="Summaries need a language model"></app-llm-dormant>
                                    } @else {
                                        <div class="flex flex-col items-center justify-center py-12 text-gray-600 gap-3">
                                            <svg xmlns="http://www.w3.org/2000/svg" class="w-12 h-12 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                                            <span class="italic font-medium">No summary available yet.</span>
                                            <button (click)="generateSummary()" *ngIf="!isGeneratingSummary" class="mt-2 px-4 py-2 bg-white/5 hover:bg-white/10 text-gray-300 rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
                                                Generate Manual Summary
                                            </button>

                                            <div *ngIf="isGeneratingSummary" class="w-full max-w-xs mt-3">
                                                <div class="flex justify-between text-xs text-gray-400 mb-1">
                                                    <span>Generating summary...</span>
                                                    <span>{{ currentProgress }}%</span>
                                                </div>
                                                <div class="h-2 bg-white/10 rounded-full overflow-hidden">
                                                    <div class="h-full bg-primary transition-all duration-300 ease-out" [style.width.%]="currentProgress"></div>
                                                </div>
                                            </div>
                                        </div>
                                    }
                                </div>
                            }

                            <!-- Index Tab -->
                            @if (activeTab === 'index') {
                                <div class="text-base leading-relaxed text-gray-200">
                                    @if (loadingSections) {
                                        <div class="flex flex-col items-center justify-center py-12 text-gray-600 gap-3">
                                            <div class="loading loading-spinner loading-lg text-primary"></div>
                                            <span class="italic font-medium">Loading sections...</span>
                                        </div>
                                    } @else if (sections.length) {
                                        <div class="space-y-6">
                                            @for (section of sections; track section.id) {
                                                <div class="space-y-3">
                                                    <!-- Section Header -->
                                                    <div class="flex items-start justify-between gap-3">
                                                        <h5 class="font-semibold text-lg text-gray-200 flex-1">
                                                            {{ section.title }}
                                                        </h5>
                                                        <div class="flex items-center gap-2 shrink-0">
                                                            @if (section.start_page) {
                                                                <span class="text-xs text-gray-500 font-mono bg-white/5 px-2 py-1 rounded">
                                                                    @if (section.end_page && section.end_page !== section.start_page) {
                                                                        pp. {{ section.start_page }}-{{ section.end_page }}
                                                                    } @else {
                                                                        p. {{ section.start_page }}
                                                                    }
                                                                </span>
                                                            }
                                                        </div>
                                                    </div>

                                                    <!-- Section Content -->
                                                    @if (section.content) {
                                                        <div class="text-sm text-gray-300 pl-4 border-l-2 border-primary/30">
                                                            <app-markdown-display [content]="section.content"></app-markdown-display>
                                                        </div>
                                                    }

                                                    <!-- Section Metadata -->
                                                    @if (section.metadata && hasVisibleMetadata(section.metadata)) {
                                                        <details class="pl-4">
                                                            <summary class="text-xs text-gray-500 cursor-pointer hover:text-gray-400 transition-colors font-medium uppercase tracking-wider">Metadata</summary>
                                                            <div class="mt-2 text-xs text-gray-400 bg-black/20 rounded p-3">
                                                                <pre class="font-mono whitespace-pre-wrap break-words">{{ formatMetadata(section.metadata) }}</pre>
                                                            </div>
                                                        </details>
                                                    }
                                                </div>
                                            }
                                        </div>
                                    } @else {
                                        <div class="flex flex-col items-center justify-center py-12 text-gray-600 gap-3">
                                            <svg xmlns="http://www.w3.org/2000/svg" class="w-12 h-12 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
                                            <span class="italic font-medium">No section index available.</span>
                                        </div>
                                    }
                                </div>
                            }

                            <!-- Key Concepts Tab -->
                            @if (activeTab === 'concepts') {
                                <div class="text-base leading-relaxed text-gray-200">
                                    @if (getKeyConcepts()?.length) {
                                        <div class="space-y-2">
                                            @for (concept of getKeyConcepts(); track concept.term) {
                                                <div [class.space-y-1]="concept.description">
                                                    <div class="flex items-start gap-2">
                                                        <span class="text-primary shrink-0 mt-1">•</span>
                                                        <div class="flex-1">
                                                            <div class="flex items-center gap-2 flex-wrap">
                                                                <button (click)="navigateToWiki(concept.term)" class="font-semibold text-gray-200 hover:text-primary transition-colors text-left">
                                                                    {{ concept.term }}
                                                                </button>
                                                                @if (concept.relevance) {
                                                                    <span class="text-xs px-2 py-0.5 rounded bg-primary/20 text-primary">{{ concept.relevance }}/10</span>
                                                                }
                                                            </div>
                                                            @if (concept.description) {
                                                                <div class="text-sm text-gray-400 mt-1">
                                                                    <app-markdown-display [content]="concept.description"></app-markdown-display>
                                                                </div>
                                                            }
                                                        </div>
                                                    </div>
                                                </div>
                                            }
                                        </div>
                                    } @else {
                                        <div class="flex flex-col items-center justify-center py-12 text-gray-600 gap-3">
                                            <svg xmlns="http://www.w3.org/2000/svg" class="w-12 h-12 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
                                            <span class="italic font-medium">No key concepts available.</span>
                                        </div>
                                    }
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
                    <div *ngIf="document?.comment" class="space-y-3">
                        <div class="flex items-center gap-2 px-1">
                            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                            <h4 class="font-semibold text-sm uppercase tracking-wider text-gray-500">Comment</h4>
                        </div>
                        <div class="text-base leading-relaxed text-gray-300">
                            <app-markdown-display [content]="document!.comment!"></app-markdown-display>
                        </div>
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
                     <button (click)="showTechnical = !showTechnical" class="w-full flex items-center justify-between text-sm font-semibold text-gray-400 hover:text-primary transition-colors mb-3 group">
                        <div class="flex items-center gap-2">
                            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 opacity-60" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>
                            <span class="uppercase tracking-wider text-xs">Technical Metadata</span>
                        </div>
                        <svg [class.rotate-180]="showTechnical" class="w-4 h-4 transition-transform opacity-60 group-hover:opacity-100" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                     </button>
                     <div *ngIf="showTechnical" class="space-y-2 animate-fade-in">
                        <!-- File Info -->
                        <div class="bg-black/30 rounded-lg p-3 space-y-2">
                            <div class="flex justify-between text-xs">
                                <span class="text-gray-500 font-medium">File Type</span>
                                <span class="text-gray-300 font-mono">{{ document?.file_type || 'N/A' }}</span>
                            </div>
                            <div class="flex justify-between text-xs">
                                <span class="text-gray-500 font-medium">File Size</span>
                                <span class="text-gray-300 font-mono">{{ formatBytes(getMetadataValue('file_size')) }}</span>
                            </div>
                            <div class="flex justify-between text-xs">
                                <span class="text-gray-500 font-medium">Document ID</span>
                                <span class="text-gray-300 font-mono text-[10px] truncate max-w-[200px]">{{ document?.id || 'N/A' }}</span>
                            </div>
                        </div>

                        <!-- Processing Info -->
                        <div *ngIf="hasProcessingInfo()" class="bg-black/30 rounded-lg p-3 space-y-2">
                            <div class="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider">Processing</div>
                            <div *ngIf="getMetadataValue('chunk_count')" class="flex justify-between text-xs">
                                <span class="text-gray-500 font-medium">Chunks</span>
                                <span class="text-gray-300 font-mono">{{ getMetadataValue('chunk_count') }}</span>
                            </div>
                            <div *ngIf="getMetadataValue('pages')" class="flex justify-between text-xs">
                                <span class="text-gray-500 font-medium">Pages</span>
                                <span class="text-gray-300 font-mono">{{ getMetadataValue('pages') }}</span>
                            </div>
                            <div *ngIf="getMetadataValue('duration')" class="flex justify-between text-xs">
                                <span class="text-gray-500 font-medium">Duration</span>
                                <span class="text-gray-300 font-mono">{{ formatDuration(getMetadataValue('duration')) }}</span>
                            </div>
                        </div>

                        <!-- Raw JSON -->
                        <details class="bg-black/30 rounded-lg overflow-hidden">
                            <summary class="p-3 text-xs font-medium text-gray-500 cursor-pointer hover:bg-white/5 transition-colors uppercase tracking-wider">Raw JSON</summary>
                            <div class="p-3 pt-0">
                                <pre class="text-[10px] text-gray-400 font-mono overflow-x-auto custom-scrollbar whitespace-pre-wrap break-all leading-relaxed">{{ document?.metadata | json }}</pre>
                            </div>
                        </details>
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
export class LibraryDocumentModalComponent implements OnChanges {
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

  llmAvailability = inject(LlmAvailabilityService);

  // UI toggle
  showTechnical = false;
  isGeneratingSummary = false;
  currentProgress = 0;
  pollInterval: any;
  activeTab: 'summary' | 'index' | 'concepts' = 'summary';

  // Sections data
  sections: DocumentSection[] = [];
  loadingSections = false;

  private modalService = inject(ModalService);

  constructor(private http: HttpClient, private router: Router) { }

  ngOnChanges(changes: SimpleChanges): void {
    // Load sections when document changes and modal opens
    if (changes['document'] && this.document?.id || changes['isOpen'] && this.isOpen && this.document?.id) {
      this.loadSections();
    }
  }

  loadSections(): void {
    if (!this.document?.id) return;

    this.loadingSections = true;
    this.http.get<DocumentSection[]>(`/api/documents/${this.document.id}/sections`).subscribe({
      next: (sections) => {
        this.sections = sections;
        this.loadingSections = false;
      },
      error: (err) => {
        console.error('Failed to load sections', err);
        this.sections = [];
        this.loadingSections = false;
      }
    });
  }

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

  generateSummary() {
    if (!this.document) return;
    this.isGeneratingSummary = true;
    this.currentProgress = 0;

    this.http.post(`/api/documents/${this.document.id}/summary`, {}).subscribe({
      next: () => {
        // Start Polling
        this.pollProgress();
      },
      error: (err) => {
        this.isGeneratingSummary = false;
        console.error('Failed to trigger summary generation', err);
        alert('Failed to start summary generation');
      }
    });
  }

  pollProgress() {
    if (this.pollInterval) clearInterval(this.pollInterval);

    this.pollInterval = setInterval(() => {
      if (!this.document) {
        clearInterval(this.pollInterval);
        return;
      }

      this.http.get<any>(`/api/documents/${this.document.id}/status`).subscribe({
        next: (statusData) => {
          this.currentProgress = statusData.progress || 0;

          if (statusData.status === 'completed' || (statusData.progress === 100)) {
            clearInterval(this.pollInterval);
            this.isGeneratingSummary = false;
            this.currentProgress = 100;
            // Reload document to get the new summary
            // We can emit a refresh or just fetch it here.
            // For now, let's close and reopen or just emit close/open logic if parent handles it.
            // Better: fetch document details locally
            this.refreshDocument();
          } else if (statusData.status === 'error') {
            clearInterval(this.pollInterval);
            this.isGeneratingSummary = false;
            alert('Summary generation failed: ' + statusData.error);
          }
        },
        error: (err) => {
          console.error('Error polling status', err);
          // Don't stop immediately on one error, could be network blip
        }
      });
    }, 1000);
  }

  refreshDocument() {
    if (!this.document) return;
    // We don't have a direct get-doc method here easily without service, 
    // but we can ask parent to refresh or just Hack it via property update if we had the content.
    // Since we don't have the content in status, let's just emit 'onSave' to trick parent to reload?
    // Or better, let's just close and let user re-open, OR simply alert user.
    // Actually, let's update the specific field if we can fetch it.
    // We'll emit a custom event or just close. 
    // User experience: It finishes, bar fills.
    // We want to see the summary.
    // Let's reload the page content? No.
    this.onSave.emit(this.document); // This might trigger parent refresh

    // Let's try to fetch the updated document logic
    // Ideally we should inject a DocumentService but we are using HttpClient raw.
    // Let's just fetch it.
    // But we don't have the endpoint mapping in this component easily.
    // Wait, we can simple trigger a reload from parent if we had an event.
    // onSave emits partial document.

    // For now, let's just show "Done" and let user close/reopen or wait for parent refresh if it happens.
    // Actually, let's reload the current window? No.

    // Hack: force reload by fetching list again via output?
    // "onSave" is usually for updates.
    // Let's just alert "Summary Generated! Please re-open the file details."
    // Or better:
    // use onSave to signal change.
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

  // --- Open Document Viewer ---

  getActionButtonText(): string {
    if (!this.document) return 'OPEN';

    const fileType = this.document.file_type;

    if (fileType === 'video' || fileType === 'youtube') {
      return 'WATCH';
    } else if (fileType === 'audio') {
      return 'LISTEN';
    } else {
      return 'READ';
    }
  }

  openDocument() {
    if (!this.document) return;

    const fileType = this.document.file_type;

    if (fileType === 'pdf' || this.document.original_filename?.toLowerCase().endsWith('.pdf')) {
      this.modalService.openPdfViewer(this.document);
    } else if (fileType === 'youtube') {
      const url = this.document.youtube_url;
      if (url) {
        this.modalService.openYoutubeViewer(url);
      } else {
        alert('YouTube URL not found for this video');
      }
    } else if (fileType === 'video' || fileType === 'audio') {
      const url = ApiEndpoints.DOCUMENT_CONTENT(this.document.id);
      this.modalService.openVideoPlayer(url);
    } else {
      // For other file types, you might want to download or show a message
      alert('Viewer not available for this file type');
    }
  }

  // --- Metadata Helper Methods ---

  getMetadataValue(key: string): any {
    if (!this.document?.metadata) return null;
    const meta = this.document.metadata as any;
    return meta[key];
  }

  hasProcessingInfo(): boolean {
    return !!(
      this.getMetadataValue('chunk_count') ||
      this.getMetadataValue('pages') ||
      this.getMetadataValue('duration')
    );
  }

  formatBytes(bytes: any): string {
    if (!bytes || isNaN(bytes)) return 'N/A';
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 Bytes';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + ' ' + sizes[i];
  }

  formatDuration(seconds: any): string {
    if (!seconds || isNaN(seconds)) return 'N/A';
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hrs > 0) {
      return `${hrs}h ${mins}m ${secs}s`;
    } else if (mins > 0) {
      return `${mins}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  }

  // --- Tab Content Helpers ---

  hasVisibleMetadata(metadata: any): boolean {
    if (!metadata || typeof metadata !== 'object') return false;
    return Object.keys(metadata).length > 0;
  }

  formatMetadata(metadata: any): string {
    if (!metadata) return '';
    try {
      return JSON.stringify(metadata, null, 2);
    } catch (e) {
      return String(metadata);
    }
  }

  getKeyConcepts(): Array<{ term: string; description?: string; relevance?: number }> | null {
    let concepts: any[] | null = null;

    // First, try document-level metadata
    if (this.document?.metadata) {
      const meta = this.document.metadata as any;

      if (meta.key_concepts && Array.isArray(meta.key_concepts)) {
        concepts = meta.key_concepts;
      } else if (meta.concepts && Array.isArray(meta.concepts)) {
        concepts = meta.concepts;
      } else if (meta.terms && Array.isArray(meta.terms)) {
        concepts = meta.terms;
      }
    }

    // If not found in document metadata, aggregate from sections
    if (!concepts && this.sections.length > 0) {
      const allConcepts: any[] = [];
      this.sections.forEach(section => {
        if (section.metadata) {
          const sectionMeta = section.metadata as any;
          if (sectionMeta.key_concepts && Array.isArray(sectionMeta.key_concepts)) {
            allConcepts.push(...sectionMeta.key_concepts);
          } else if (sectionMeta.concepts && Array.isArray(sectionMeta.concepts)) {
            allConcepts.push(...sectionMeta.concepts);
          }
        }
      });

      // Remove duplicates and transform to expected format
      if (allConcepts.length > 0) {
        const uniqueConcepts = new Map<string, any>();
        allConcepts.forEach(concept => {
          const name = typeof concept === 'string' ? concept : concept.name;
          if (name && !uniqueConcepts.has(name)) {
            uniqueConcepts.set(name, concept);
          }
        });
        concepts = Array.from(uniqueConcepts.values());
      }
    }

    if (!concepts || concepts.length === 0) return null;

    // Transform concepts to expected format
    return concepts.map(item => {
      if (typeof item === 'string') {
        return { term: item, description: undefined };
      }
      // Transform objects with 'name' property to use 'term' instead
      if (item.name) {
        return {
          term: item.name,
          description: item.description || undefined,
          relevance: item.relevance
        };
      }
      // Return as-is if it already has 'term' property
      return item;
    });
  }

  navigateToWiki(conceptName: string): void {
    this.router.navigate(['/wiki', conceptName]);
  }
}
