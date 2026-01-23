import { Component, ElementRef, ViewChild, input, effect, AfterViewInit, OnDestroy, signal, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import cytoscape from 'cytoscape';

@Component({
    selector: 'app-graph-visualizer',
    standalone: true,
    imports: [CommonModule],
    template: `
    <div #graphContainer class="graph-container rounded-xl border border-divider overflow-hidden relative" [style.height.px]="height()">
        <!-- Header -->
        <div class="absolute top-2 left-2 z-10 flex items-center gap-2">
            <div class="px-2 py-0.5 bg-panel/80 backdrop-blur-sm border border-divider rounded-full text-[10px] font-medium text-secondary">Reasoning Graph</div>
        </div>

        <!-- Fullscreen Button -->
         <button (click)="toggleFullscreen()" class="absolute top-2 right-2 z-10 p-1.5 bg-panel/80 backdrop-blur-sm border border-divider rounded-lg text-secondary hover:text-primary hover:bg-white/5 transition-colors" title="Toggle Fullscreen">
            <svg *ngIf="!isFullscreen()" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>
            <svg *ngIf="isFullscreen()" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"/></svg>
        </button>
        
        <!-- Cytoscape Container -->
        <div #cy id="cy" class="w-full h-full bg-base"></div>

        <!-- Details Overlay -->
        @if (selectedNode()) {
            <div class="absolute bottom-4 right-4 z-20 w-72 max-h-[200px] overflow-y-auto p-4 bg-base/95 backdrop-blur shadow-xl border border-primary/20 rounded-lg text-xs transition-all animate-in slide-in-from-bottom-2">
                <div class="flex justify-between items-start gap-2 mb-2">
                    <h3 class="font-bold text-sm text-primary">{{ selectedNode().label }}</h3>
                    <button (click)="selectedNode.set(null)" class="text-secondary hover:text-primary">
                        <span class="text-lg leading-none">&times;</span>
                    </button>
                </div>
                
                @if (selectedNode().full_desc) {
                    <div class="mb-3 opacity-90 leading-relaxed">
                        {{ selectedNode().full_desc }}
                    </div>
                }
                
                @if (selectedNode().source_document_id) {
                    <div class="pt-2 border-t border-divider">
                        <div class="flex items-center gap-2">
                            <span class="opacity-60">Source:</span>
                            <button (click)="onViewSource(selectedNode())" 
                                    class="text-xs bg-primary/10 hover:bg-primary/20 text-primary px-2 py-1 rounded transition-colors max-w-[200px] truncate"
                                    [title]="selectedNode().source_document_title">
                                View {{ selectedNode().source_document_title || 'Document' }}
                            </button>
                        </div>
                    </div>
                }
            </div>
        }
    </div>
  `,
    styles: [`
    :host { display: block; width: 100%; }
    .graph-container { background-color: var(--color-base, #1e1e1e); }
  `]
})
export class GraphVisualizerComponent implements AfterViewInit, OnDestroy {
    data = input.required<any>();
    height = input<number>(300);

    // Outputs
    viewSource = output<any>();

    // State
    selectedNode = signal<any>(null);
    isFullscreen = signal(false);

    @ViewChild('cy') cyElement!: ElementRef;
    @ViewChild('graphContainer') graphContainer!: ElementRef; // We need to reference the container div
    private cy: cytoscape.Core | null = null;

    constructor() {
        effect(() => {
            const graphData = this.data();
            if (this.cy && graphData) {
                this.renderGraph(graphData);
            }
        });
    }

    ngAfterViewInit() {
        this.setupFullscreenListener();
        this.initGraph();
        if (this.data()) {
            this.renderGraph(this.data());
        }
    }

    ngOnDestroy() {
        if (this.cy) {
            this.cy.destroy();
        }
    }

    onViewSource(node: any) {
        this.viewSource.emit({
            id: node.source_document_id,
            title: node.source_document_title || 'Document',
            type: node.source_document_type || 'unknown',
            original_filename: node.original_filename,
            page_number: node.page_number,
            start_time: node.start_time
        });
    }

    initGraph() {
        this.cy = cytoscape({
            container: this.cyElement.nativeElement,
            elements: [],
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
                        'height': 40,
                        'font-size': '10px',
                        'text-wrap': 'wrap',
                        'text-max-width': '80px'
                    }
                },
                {
                    selector: 'node[type="hyperedge"]',
                    style: {
                        'background-color': '#888888',
                        'shape': 'round-rectangle',
                        'width': 20,
                        'height': 20,
                        'font-size': '8px'
                    }
                },
                {
                    selector: ':selected',
                    style: {
                        'border-width': 2,
                        'border-color': '#fff',
                        'background-color': '#FFD700'
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'width': 2,
                        'line-color': '#ccc',
                        'target-arrow-color': '#ccc',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        'font-size': '8px',
                        'text-rotation': 'autorotate'
                    }
                }
            ],
            layout: {
                name: 'grid'
            },
            userZoomingEnabled: true,
            userPanningEnabled: true
        });

        // Event Listeners
        this.cy.on('tap', 'node', (evt: any) => {
            const nodeData = evt.target.data();
            this.selectedNode.set(nodeData);
        });

        this.cy.on('tap', (evt: any) => {
            if (evt.target === this.cy) {
                this.selectedNode.set(null);
            }
        });
    }

    renderGraph(data: any) {
        if (!this.cy) return;

        this.cy.elements().remove();
        this.cy.add(data);

        this.cy.layout({
            name: 'cose',
            animate: true,
            animationDuration: 500,
            padding: 50,
            // @ts-ignore
            componentSpacing: 40,
            nodeOverlap: 4,
            refresh: 20,
            fit: true,
            randomize: false
        }).run();

        this.cy.fit();
    }

    toggleFullscreen() {
        const elem = this.graphContainer.nativeElement;

        if (!document.fullscreenElement) {
            elem.requestFullscreen().catch((err: any) => {
                console.error(`Error attempting to enable fullscreen mode: ${err.message} (${err.name})`);
            });
        } else {
            document.exitFullscreen();
        }
    }

    private setupFullscreenListener() {
        document.addEventListener('fullscreenchange', this.handleFullscreenChange.bind(this));
    }

    private handleFullscreenChange() {
        const isFull = !!document.fullscreenElement;
        this.isFullscreen.set(isFull);
        // Resize graph after transition
        setTimeout(() => {
            if (this.cy) {
                this.cy.resize();
                this.cy.fit();
            }
        }, 100);
    }
}
