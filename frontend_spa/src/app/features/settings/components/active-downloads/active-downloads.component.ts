import { Component, OnInit, OnDestroy, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SettingsService } from '../../../../services/settings.service';
import { interval, Subscription, switchMap } from 'rxjs';

@Component({
    selector: 'app-active-downloads',
    standalone: true,
    imports: [CommonModule],
    templateUrl: './active-downloads.component.html'
})
export class ActiveDownloadsComponent implements OnInit, OnDestroy {
    settingsService = inject(SettingsService);

    downloads = signal<any[]>([]);
    private pollingSub: Subscription | null = null;

    ngOnInit() {
        // Poll active downloads every 2 seconds
        this.pollingSub = interval(2000).pipe(
            switchMap(() => this.settingsService.getActiveDownloads())
        ).subscribe({
            next: (data) => {
                // data structure expected: { "tasks": [ { "task_id": "...", "model_name": "...", "status": "...", "progress": ... } ] }
                if (data && data.tasks) {
                    this.downloads.set(data.tasks);
                } else {
                    this.downloads.set([]);
                }
            },
            error: (err) => console.error('Error polling downloads:', err)
        });
    }

    ngOnDestroy() {
        if (this.pollingSub) {
            this.pollingSub.unsubscribe();
        }
    }
}
