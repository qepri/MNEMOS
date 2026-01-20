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
            },
            {
                path: 'library',
                loadComponent: () => import('./features/library/library.component').then(m => m.LibraryPageComponent)
            },
            {
                path: 'collections',
                loadComponent: () => import('./features/collections/collections.component').then(m => m.CollectionsPageComponent)
            }
        ]
    }
];
