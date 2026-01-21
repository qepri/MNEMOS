import { Component, ElementRef, ViewChild, inject, signal, effect, OnDestroy, AfterViewInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ReasoningService } from '../../services/reasoning.service';
import { ToastrService } from 'ngx-toastr';
import cytoscape from 'cytoscape';

@Component({
    selector: 'app-reasoning',
    standalone: true,
    imports: [CommonModule, FormsModule],
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
            <span *ngIf="isReprocessing()" class="loading-dots">
                <span></span><span></span><span></span>
            </span>
            {{ isReprocessing() ? 'Building Graph...' : 'Rebuild Knowledge Graph' }}
        </button>
      </div>

      <!-- Controls -->
      <div class="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr_auto] gap-4 items-end bg-panel p-4 rounded-xl shadow-lg border border-divider">
        
        <!-- Start -->
        <div class="flex flex-col gap-2 w-full">
            <label class="text-sm font-semibold text-primary">Start Concept</label>
            <input type="text" [(ngModel)]="startConcept" placeholder="e.g. PCL" 
                class="w-full px-4 py-2 bg-input border border-divider rounded-lg focus:outline-none focus:ring-2 focus:ring-accent text-primary placeholder-secondary transition-all" />
        </div>

        <!-- Arrow Icon -->
        <div class="hidden md:flex pb-3 text-secondary">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
        </div>

        <!-- Goal -->
        <div class="flex flex-col gap-2 w-full">
            <label class="text-sm font-semibold text-primary">Goal Concept</label>
            <input type="text" [(ngModel)]="goalConcept" placeholder="e.g. Bone Healing" 
                class="w-full px-4 py-2 bg-input border border-divider rounded-lg focus:outline-none focus:ring-2 focus:ring-accent text-primary placeholder-secondary transition-all" />
        </div>

        <!-- Action -->
        <button (click)="traverse()" [disabled]="isLoading() || !startConcept || !goalConcept" 
            class="h-[42px] px-6 bg-accent hover:bg-accent-dark text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center min-w-[120px]">
            <span *ngIf="isLoading()" class="loading-dots mr-2">
                <span></span><span></span><span></span>
            </span>
            Traverse Path
        </button>
      </div>

      <!-- Results Area -->
      <div class="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 min-h-0">
        
        <!-- Graph Visualization (Left/Top) -->
        <div class="lg:col-span-2 bg-base rounded-xl border border-divider relative overflow-hidden flex flex-col shadow-sm">
            <div class="absolute top-4 left-4 z-10 px-3 py-1 bg-panel/80 backdrop-blur-sm border border-divider rounded-full text-xs font-medium text-secondary">Graph View</div>
            <div #cy id="cy" class="w-full h-full bg-base"></div>
        </div>

        <!-- Narrative / Text (Right/Bottom) -->
        <div class="bg-panel rounded-xl p-6 overflow-y-auto border border-divider shadow-sm">
            <h3 class="text-xl font-bold mb-4 flex items-center gap-2 text-primary">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Hypothesis Narrative
            </h3>
            
            <div *ngIf="!result()" class="text-secondary italic flex flex-col items-center justify-center h-40">
                <span>Enter concepts to generate a hypothesis...</span>
            </div>

            <div *ngIf="result()" class="prose prose-sm max-w-none text-primary animate-fade-in">
                <p class="whitespace-pre-wrap leading-relaxed">{{ result() }}</p>
            </div>
        </div>
      </div>
    </div>
  `,
    styles: [`
    :host {
      display: block;
      height: 100%;
    }
    #cy {
        display: block;
        min-height: 400px;
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
    @ViewChild('cy') cyElement!: ElementRef;

    private reasoningService = inject(ReasoningService);
    private toastr = inject(ToastrService);

    // Inputs
    startConcept = '';
    goalConcept = '';

    // State
    isLoading = signal(false);
    isReprocessing = signal(false);
    result = signal<string>('');

    // Cytoscape Instance
    private cy: cytoscape.Core | null = null;

    ngAfterViewInit() {
        this.initGraph();
    }

    ngOnDestroy() {
        if (this.cy) {
            this.cy.destroy();
        }
    }

    initGraph() {
        // Basic initialization of Cytoscape
        this.cy = cytoscape({
            container: this.cyElement.nativeElement,
            elements: [], // start empty
            style: [
                {
                    selector: 'node',
                    style: {
                        'background-color': '#66CCFF',
                        'label': 'data(label)',
                        'color': '#fff',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'width': 40,
                        'height': 40
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'width': 3,
                        'line-color': '#ccc',
                        'target-arrow-color': '#ccc',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier'
                    }
                }
            ],
            layout: {
                name: 'grid',
                rows: 1
            }
        });
    }

    traverse() {
        if (!this.startConcept || !this.goalConcept) return;

        this.isLoading.set(true);
        this.result.set('');

        // Clear previous graph
        if (this.cy) {
            this.cy.elements().remove();
        }

        this.reasoningService.traverse(this.startConcept, this.goalConcept).subscribe({
            next: (res: any) => {
                this.result.set(res.narrative);
                this.isLoading.set(false);
                this.toastr.success('Hypothesis generated successfully');

                if (this.cy && res.graph_data) {
                    this.cy.add(res.graph_data);

                    // Use COSE layout for better organic dispersal
                    this.cy.layout({
                        name: 'cose',
                        animate: true,
                        animationDuration: 500,
                        padding: 50
                    }).run();
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
                // In a real app, we'd poll for status. For now, we assume queued.
                setTimeout(() => this.isReprocessing.set(false), 3000);
            },
            error: (err) => {
                this.toastr.error("Failed to trigger reprocessing");
                this.isReprocessing.set(false);
            }
        });
    }
}
