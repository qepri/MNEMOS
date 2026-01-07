import { Routes } from '@angular/router';
import { ChatPage } from './features/chat/pages/chat-page/chat-page.component';

export const routes: Routes = [
    {
        path: '',
        loadComponent: () => import('./layouts/main-layout/main-layout').then(m => m.MainLayout),
        children: [
            {
                path: '',
                component: ChatPage
            },
            {
                path: 'settings',
                loadComponent: () => import('./features/settings/pages/settings-page.component').then(m => m.SettingsPage)
            }
        ]
    }
];
