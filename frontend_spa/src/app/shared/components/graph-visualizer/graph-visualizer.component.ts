import { Component, ElementRef, ViewChild, input, effect, AfterViewInit, OnDestroy, signal, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import cytoscape from 'cytoscape';

@Component({
    selector: 'app-graph-visualizer',
    standalone: true,
    imports: [CommonModule],
    template: `
    <div class="graph-container rounded-xl border border-divider overflow-hidden relative" [style.height.px]="height()">
        <!-- Header -->
        <div class="absolute top-2 left-2 z-10 px-2 py-0.5 bg-panel/80 backdrop-blur-sm border border-divider rounded-full text-[10px] font-medium text-secondary">Reasoning Graph</div>
        
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
                            <button (click)="onViewSource(selectedNode().source_document_id)" 
                                    class="text-xs bg-primary/10 hover:bg-primary/20 text-primary px-2 py-1 rounded transition-colors">
                                View Document
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
    viewSource = output<string>();

    // State
    selectedNode = signal<any>(null);

    @ViewChild('cy') cyElement!: ElementRef;
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

    onViewSource(docId: string) {
        this.viewSource.emit(docId);
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
                        'font-size': '8px',
                        'label': ''  // Hide label on graph to reduce clutter? Or keep it? keeping it for now
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
}
