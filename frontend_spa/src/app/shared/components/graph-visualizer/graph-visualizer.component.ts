import { Component, ElementRef, ViewChild, input, effect, AfterViewInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import cytoscape from 'cytoscape';

@Component({
    selector: 'app-graph-visualizer',
    standalone: true,
    imports: [CommonModule],
    template: `
    <div class="graph-container rounded-xl border border-divider overflow-hidden relative" [style.height.px]="height()">
        <div class="absolute top-2 left-2 z-10 px-2 py-0.5 bg-panel/80 backdrop-blur-sm border border-divider rounded-full text-[10px] font-medium text-secondary">Reasoning Graph</div>
        <div #cy id="cy" class="w-full h-full bg-base"></div>
    </div>
  `,
    styles: [`
    :host { display: block; width: 100%; }
    .graph-container { background-color: var(--color-base, #1e1e1e); }
  `]
})
export class GraphVisualizerComponent implements AfterViewInit, OnDestroy {
    data = input.required<any>();
    height = input<number>(300); // Default height

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
        // Initial render if data exists
        if (this.data()) {
            this.renderGraph(this.data());
        }
    }

    ngOnDestroy() {
        if (this.cy) {
            this.cy.destroy();
        }
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
                        'font-size': '10px'
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
    }

    renderGraph(data: any) {
        if (!this.cy) return;

        this.cy.elements().remove();
        this.cy.add(data);

        this.cy.layout({
            name: 'cose',
            animate: true,
            animationDuration: 500,
            padding: 50
        }).run();

        this.cy.fit();
    }
}
