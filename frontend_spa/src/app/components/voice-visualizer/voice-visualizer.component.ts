import { Component, ElementRef, ViewChild, AfterViewInit, OnDestroy, effect, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { VoiceService } from '@services/voice.service';
import anime from 'animejs/lib/anime.es.js';

@Component({
    selector: 'app-voice-visualizer',
    standalone: true,
    imports: [CommonModule],
    template: `
    <div class="visualizer-container">
      <div class="status-container">
          <div class="status-text">{{ statusText }}</div>
          <div class="transcript-text" *ngIf="voiceService.lastVadTranscript()">
              Heard: "{{ voiceService.lastVadTranscript() }}"
          </div>
          <div style="color: #666; font-size: 0.8rem; margin-top: 0.5rem;">
            Vol: {{ (voiceService.currentVolume() * 100).toFixed(1) }}% (Thresh: 2%)
          </div>
      </div>
      <div class="dots-wrapper" #wrapper></div>
    </div>
  `,
    styles: [`
    .visualizer-container {
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: #111;
      display: flex;
      justify-content: center;
      align-items: center;
      z-index: 50;
      overflow: hidden;
    }
    
    .status-container {
        position: absolute;
        top: 15%;
        width: 100%;
        text-align: center;
        z-index: 60;
        pointer-events: none;
    }
    
    .status-text {
        color: white;
        font-family: monospace;
        font-size: 1.5rem;
        letter-spacing: 4px;
        text-transform: uppercase;
        margin-bottom: 1rem;
        text-shadow: 0 0 10px rgba(255,255,255,0.5);
    }
    
    .transcript-text {
        font-family: 'Inter', sans-serif;
        color: #888;
        font-size: 1rem;
        background: rgba(0,0,0,0.5);
        padding: 0.5rem 1rem;
        border-radius: 99px;
        display: inline-block;
    }

    .dots-wrapper {
      position: relative;
      width: 100%;
      height: 100%;
      display: flex;
      justify-content: center;
      align-items: center;
    }

    /* Dynamically created dot styles */
    :host ::ng-deep .dot {
      position: absolute;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      /* Centering logic handled by Translate */
    }
  `]
})
export class VoiceVisualizerComponent implements AfterViewInit, OnDestroy {
    voiceService = inject(VoiceService);

    @ViewChild('wrapper') wrapper!: ElementRef;

    private animation: any;
    private loopInterval: any;
    private dots: HTMLElement[] = [];

    // Settings for Colorful Spiral
    private readonly DOT_COUNT = 300; // Increased density

    get statusText() {
        const state = this.voiceService.vadState();
        switch (state) {
            case 'idle': return 'Waiting...';
            case 'listening': return 'Listening...';
            case 'processing': return 'Thinking...';
            case 'speaking': return 'Speaking...';
            default: return 'Zenia';
        }
    }

    constructor() {
        effect(() => {
            // React to state changes if needed for major animation switches
            const state = this.voiceService.vadState();
        });
    }

    ngAfterViewInit() {
        this.createDots();
        this.startAnimationLoop();
    }

    ngOnDestroy() {
        if (this.loopInterval) cancelAnimationFrame(this.loopInterval);
        if (this.animation) this.animation.pause();
        anime.remove(this.dots);
    }

    private createDots() {
        const wrapperEl = this.wrapper.nativeElement;

        // Colorful Spiral Logic (Phyllotaxis)
        // Angle = index * 137.5 degrees (Golden Angle) if we want pure phyllotaxis
        // The user example used: angle = utils.mapRange(0, count, 0, Math.PI * 100);
        // Let's replicate a nice spiral.

        for (let i = 0; i < this.DOT_COUNT; i++) {
            const dot = document.createElement('div');
            dot.classList.add('dot');

            // Color: Rainbow HSL
            const hue = Math.round((360 / this.DOT_COUNT) * i);
            dot.style.backgroundColor = `hsl(${hue}, 60%, 60%)`;

            wrapperEl.appendChild(dot);
            this.dots.push(dot);
        }

        // Initial Layout: Spiral
        // Distance from center usually sqrt(i) for uniform packing
        anime.set(this.dots, {
            translateX: 0,
            translateY: 0,
            scale: 0
        });
    }

    private startAnimationLoop() {
        const animate = () => {
            const dataArray = this.voiceService.getAudioFrequencyData();
            const state = this.voiceService.vadState();

            const time = Date.now() * 0.0002; // Slow rotation

            // Volume calc
            let volume = 0;
            if (dataArray) {
                let sum = 0;
                for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
                volume = (sum / dataArray.length) / 255;
            }

            const baseSpread = state === 'listening' ? 8 : 6;
            const maxSpread = state === 'listening' ? 12 : 8;

            // DynamicSpread breathes with volume
            const currentSpread = baseSpread + (volume * 10);

            this.dots.forEach((dot, i) => {
                // Golden Angle Phyllotaxis: 137.508 degrees
                // angle = i * 137.5 deg in radians (~2.4)
                const theta = i * 2.39996323 + (state === 'processing' ? time * 10 : time);

                // Radius = c * sqrt(i)
                const r = currentSpread * Math.sqrt(i) + (state === 'speaking' ? Math.sin(time * 20 + i * 0.2) * 5 : 0);

                const x = r * Math.cos(theta);
                const y = r * Math.sin(theta);

                // Scale
                let scale = 1;
                if (state === 'listening' && dataArray) {
                    // Map frequency to scale (higher freq = outer dots?)
                    const freqIdx = Math.floor((i / this.DOT_COUNT) * dataArray.length);
                    const val = dataArray[freqIdx] / 255;
                    scale = 0.5 + (val * 4); // More dramatic
                } else if (state === 'idle') {
                    // Gentle breathing wave
                    scale = 0.8 + Math.sin(time * 5 + r * 0.05) * 0.3;
                } else if (state === 'processing') {
                    scale = 0.6;
                } else if (state === 'speaking') {
                    scale = 1 + Math.sin(time * 30) * 0.2;
                }

                dot.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;

                // Optional: Rotate hue for rainbow flower effect over time
                if (state === 'processing') {
                    const hue = (i * 2 + time * 1000) % 360;
                    dot.style.backgroundColor = `hsl(${hue}, 60%, 60%)`;
                }
            });

            this.loopInterval = requestAnimationFrame(animate);
        };

        this.loopInterval = requestAnimationFrame(animate);
    }
}
