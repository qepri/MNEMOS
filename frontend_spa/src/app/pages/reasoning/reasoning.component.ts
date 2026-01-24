import { Component, ElementRef, ViewChild, inject, signal, effect, OnDestroy, AfterViewInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ReasoningService } from '../../services/reasoning.service';
import { ToastrService } from 'ngx-toastr';
import { CollectionService } from '../../services/collection.service';
import { ConversationsService } from '../../services/conversations.service';
import { Collection } from '../../core/models/collection.model';
import { GraphVisualizerComponent } from '../../shared/components/graph-visualizer/graph-visualizer.component';
import { Router } from '@angular/router';

@Component({
    selector: 'app-reasoning',
    standalone: true,
    imports: [CommonModule, FormsModule, GraphVisualizerComponent],
    template: `
    <div class="h-full flex flex-col gap-6 p-6">
      
      <!-- Header -->
      <div class="flex justify-between items-center">
        <div>
            <h1 class="text-3xl font-bold mb-2 text-primary">
            Reasoning Engine
            </h1>
            <p class="text-secondary">Explore hidden connections in your knowledge graph.</p>
        </div>
        
        <button 
            (click)="triggerReprocess()" 
            [disabled]="isReprocessing()"
            class="px-4 py-2 rounded-lg border border-divider text-sm font-medium text-secondary hover:bg-hover hover:text-primary transition-colors flex items-center gap-2">
            @if (isReprocessing()) {
                <span class="loading-dots">
                    <span></span><span></span><span></span>
                </span>
            }
            {{ isReprocessing() ? 'Building Graph...' : 'Rebuild Knowledge Graph' }}
        </button>
      </div>

      <!-- Controls -->
      <!-- Controls -->
      <div class="flex flex-col gap-6 bg-panel p-6 rounded-xl shadow-lg border border-divider">
        
        <!-- Collection Filter -->
        <div class="w-full">
            <label class="text-sm font-semibold text-primary mb-2 block">Context Scope (Collections)</label>
            <div class="flex flex-wrap gap-2">
                @for (col of collections(); track col.id) {
                    <button 
                        (click)="toggleCollection(col.id)"
                        [class.bg-accent]="selectedCollectionIds().has(col.id)"
                        [class.text-white]="selectedCollectionIds().has(col.id)"
                        [class.bg-input]="!selectedCollectionIds().has(col.id)"
                        [class.text-secondary]="!selectedCollectionIds().has(col.id)"
                        class="px-3 py-1 rounded-full text-xs font-medium border border-divider hover:border-accent transition-all">
                        {{ col.name }}
                    </button>
                }
                @if (collections().length === 0) {
                    <span class="text-xs text-secondary italic">No collections found.</span>
                }
            </div>
        </div>

        <!-- Inputs Row -->
        <div class="flex flex-col md:flex-row items-end gap-4">
            <!-- Start -->
            <div class="flex-1 w-full">
                <label class="text-xs font-bold text-secondary uppercase tracking-wider mb-1 block">Start From</label>
                <input type="text" [(ngModel)]="startConcept" placeholder="e.g. PCL" 
                    class="w-full h-12 px-4 bg-input border border-divider rounded-xl focus:outline-none focus:ring-2 focus:ring-accent text-lg text-primary placeholder-secondary/50 transition-all font-medium" />
            </div>

            <!-- Arrow Icon -->
            <div class="hidden md:flex pb-4 text-secondary/50">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                </svg>
            </div>

            <!-- Goal -->
            <div class="flex-1 w-full">
                <label class="text-xs font-bold text-secondary uppercase tracking-wider mb-1 block">Target Concept</label>
                <input type="text" [(ngModel)]="goalConcept" placeholder="e.g. Bone Healing" 
                    class="w-full h-12 px-4 bg-input border border-divider rounded-xl focus:outline-none focus:ring-2 focus:ring-accent text-lg text-primary placeholder-secondary/50 transition-all font-medium" />
            </div>
        </div>

        <!-- Actions Row -->
        <div class="flex flex-col md:flex-row items-center justify-between gap-4 pt-2 border-t border-divider/50">
             <!-- Advanced Controls -->
            <div class="flex items-center gap-6 bg-base-200/50 px-4 py-2 rounded-lg border border-divider/50">
                <!-- Semantic Leap Toggle -->
                <div class="flex items-center gap-3 cursor-pointer group" (click)="useSemanticLeap.set(!useSemanticLeap())">
                    <div class="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" id="semanticLeap" [ngModel]="useSemanticLeap()" (ngModelChange)="useSemanticLeap.set($event)" class="sr-only peer">
                        <div class="w-10 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-accent/50 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-accent shadow-inner"></div>
                    </div>
                    <label for="semanticLeap" class="text-sm font-medium text-primary cursor-pointer select-none group-hover:text-accent transition-colors">
                        Semantic Leap
                    </label>
                </div>
    
                <div class="h-6 w-px bg-divider"></div>
    
                <!-- Max Depth Slider -->
                <div class="flex items-center gap-3">
                    <label class="text-sm font-medium text-primary whitespace-nowrap">Depth: <span class="text-accent font-bold">{{ maxDepth() }}</span></label>
                    <input type="range" min="1" max="5" step="1" [ngModel]="maxDepth()" (ngModelChange)="maxDepth.set($event)" 
                        class="w-24 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 accent-accent" />
                </div>
            </div>

            <!-- Main Action -->
            <button (click)="traverse()" [disabled]="isLoading() || !startConcept || !goalConcept" 
                class="h-12 px-8 bg-accent hover:bg-accent-dark text-white rounded-xl font-bold tracking-wide transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center min-w-[160px] shadow-lg hover:shadow-accent/40 active:scale-95">
                @if (isLoading()) {
                    <span class="loading-dots mr-2">
                        <span></span><span></span><span></span>
                    </span>
                }
                Start Traversal
            </button>
        </div>
      </div>

      <!-- Results Area -->
      <div class="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 min-h-0">
        
        <!-- Graph Visualization (Left/Top) -->
        <div class="lg:col-span-2 bg-base rounded-xl border border-divider relative overflow-hidden flex flex-col shadow-sm">
             <app-graph-visualizer [data]="graphData()" [height]="600" (viewSource)="handleViewSource($event)"></app-graph-visualizer>
        </div>

        <!-- Narrative / Text (Right/Bottom) -->
        <div class="bg-panel rounded-xl p-6 overflow-y-auto border border-divider shadow-sm">
            <h3 class="text-xl font-bold mb-4 flex items-center gap-2 text-primary">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Hypothesis Narrative
            </h3>
            
            @if (!result()) {
                <div class="text-secondary italic flex flex-col items-center justify-center h-40">
                    <span>Enter concepts to generate a hypothesis...</span>
                </div>
            }

            @if (result()) {
                <div class="prose prose-sm max-w-none text-primary animate-fade-in">
                    <p class="whitespace-pre-wrap leading-relaxed">{{ result() }}</p>
                </div>
            }
        </div>
      </div>
    </div>
  `,
    styles: [`
    :host {
      display: block;
      height: 100%;
    }
    .animate-fade-in {
        animation: fadeIn 0.5s ease-in-out;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
  `]
})
export class ReasoningComponent implements AfterViewInit, OnDestroy {

    private reasoningService = inject(ReasoningService);
    private collectionService = inject(CollectionService);
    private conversationsService = inject(ConversationsService);
    private toastr = inject(ToastrService);
    private router = inject(Router);

    // Inputs
    startConcept = '';
    goalConcept = '';

    // State
    isLoading = signal(false);
    isReprocessing = signal(false);
    result = signal<string>('');
    graphData = signal<any>(null);
    useSemanticLeap = signal(false);
    maxDepth = signal(3);

    // Collections
    collections = signal<Collection[]>([]);
    selectedCollectionIds = signal<Set<string>>(new Set());

    constructor() {
        // Load collections
        this.collectionService.getCollections().subscribe({
            next: (cols) => this.collections.set(cols),
            error: (err) => console.error("Failed to load collections", err)
        });
    }

    ngAfterViewInit() {
        // No init needed
    }

    toggleCollection(id: string) {
        this.selectedCollectionIds.update(set => {
            const newSet = new Set(set);
            if (newSet.has(id)) {
                newSet.delete(id);
            } else {
                newSet.add(id);
            }
            return newSet;
        });
    }

    handleViewSource(docId: string) {
        this.router.navigate(['/library/documents', docId]);
    }

    ngOnDestroy() {
        // No cleanup needed
    }

    traverse() {
        if (!this.startConcept || !this.goalConcept) return;

        this.isLoading.set(true);
        this.result.set('');
        this.graphData.set(null);

        const filterIds = Array.from(this.selectedCollectionIds());

        // Always save to chat as requested
        this.reasoningService.traverse(this.startConcept, this.goalConcept, filterIds, true, this.useSemanticLeap(), this.maxDepth()).subscribe({
            next: (res: any) => {
                const result = res as any; // Explicit cast to avoid type errors with flexible response
                this.result.set(result.narrative || result.result);
                this.isLoading.set(false);
                this.toastr.success('Hypothesis generated and saved to Chat history');

                if (result.graph_data) {
                    this.graphData.set(result.graph_data);
                }

                // Refresh conversations list in sidebar so the new chat (if saved) appears immediately
                if (result.conversation_id) {
                    this.conversationsService.loadConversations();
                }
            },
            error: (err) => {
                console.error(err);
                this.toastr.error('Failed to traverse reasoning graph');
                this.isLoading.set(false);
            }
        });
    }

    triggerReprocess() {
        if (!confirm("This will scan ALL documents to build the knowledge graph. It may take a while. Continue?")) return;

        this.isReprocessing.set(true);
        this.reasoningService.reprocessAll().subscribe({
            next: (res) => {
                this.toastr.info(res.message);

                // Poll for completion
                const pollInterval = window.setInterval(() => {
                    this.reasoningService.getReprocessStatus().subscribe({
                        next: (statusRes) => {
                            if (statusRes.status !== 'processing') {
                                this.isReprocessing.set(false);
                                this.toastr.success('Knowledge Graph Rebuilt Successfully');
                                clearInterval(pollInterval);
                            }
                        },
                        error: () => {
                            this.isReprocessing.set(false);
                            clearInterval(pollInterval);
                        }
                    });
                }, 2000);
            },
            error: (err) => {
                this.toastr.error("Failed to trigger reprocessing");
                this.isReprocessing.set(false);
            }
        });
    }
}
