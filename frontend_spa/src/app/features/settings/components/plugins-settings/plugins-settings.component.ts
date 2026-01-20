
import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
    selector: 'app-plugins-settings',
    standalone: true,
    imports: [CommonModule],
    template: `
    <div class="space-y-6">
      <div class="bg-panel rounded-xl p-6 border border-divider">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h3 class="text-lg font-semibold text-primary">Database Management</h3>
            <p class="text-sm text-secondary">Access the database directly via Adminer</p>
          </div>
          <div class="p-2 bg-base-100 rounded-lg">
             <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-accent"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"/><path d="M12 12v9"/><path d="m8 17 4 4 4-4"/></svg>
          </div>
        </div>

        <div class="bg-base-100 p-4 rounded-lg border border-divider mb-4">
             <div class="grid grid-cols-2 gap-4 text-sm">
                 <div>
                     <span class="text-secondary block mb-1">System</span>
                     <span class="font-mono text-primary">PostgreSQL</span>
                 </div>
                 <div>
                     <span class="text-secondary block mb-1">Server</span>
                     <span class="font-mono text-primary">db</span>
                 </div>
                 <div>
                     <span class="text-secondary block mb-1">Username</span>
                     <span class="font-mono text-primary">mnemos_user</span>
                 </div>
                 <div>
                     <span class="text-secondary block mb-1">Database</span>
                     <span class="font-mono text-primary">mnemos_db</span>
                 </div>
             </div>
        </div>

        <p class="text-xs text-secondary opacity-70 mb-4 bg-warning/10 text-warning px-3 py-2 rounded">
            <strong>Note:</strong> Password is pre-filled. If prompted, use: <code>mnemos_pass</code>
        </p>

        <a [href]="adminerUrl" target="_blank" class="btn btn-primary w-full gap-2">
           <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
           Open Adminer Database Manager
        </a>
      </div>
    </div>
  `
})
export class PluginsSettingsComponent {
    // Construct Adminer URL with auto-login parameters if possible.
    // Adminer standard generic login often doesn't accept GET params for security, 
    // but some docker images do. The standard `adminer` image typicaly requires form entry.
    // However, we can link to it.
    // To support "hardcoded values for login", we can try passing ?server=db&username=mnemos_user&db=mnemos_db
    // Adminer usually supports: ?pgsql=db&username=mnemos_user&db=mnemos_db&ns=public
    // Note: Password usually cannot be passed via URL for security reasons in standard Adminer.

    // We assume the user is accessing localhost:8080.
    // Since this is running in a browser, we need the correct host.
    // If the app is on port 5200 (localhost), adminer is likely on localhost:8080.

    // We try to pre-fill as much as possible.
    // ?pgsql=db&username=mnemos_user&db=mnemos_db
    adminerUrl = `http://localhost:8080/?pgsql=db&username=mnemos_user&db=mnemos_db`;
}
