import { Routes } from '@angular/router';
import { ChatPage } from './features/chat/pages/chat-page.component';

export const routes: Routes = [
    {
        path: '',
        component: ChatPage
    },
    {
        path: 'settings',
        loadComponent: () => import('./features/settings/pages/settings-page.component').then(m => m.SettingsPage)
    }
];
