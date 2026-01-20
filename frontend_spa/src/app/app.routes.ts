import { Routes } from '@angular/router';
import { AppRoutes } from '@core/constants/app-routes';
import { ChatPage } from './features/chat/pages/chat-page/chat-page.component';

export const routes: Routes = [
    {
        path: AppRoutes.HOME,
        loadComponent: () => import('./layouts/main-layout/main-layout').then(m => m.MainLayout),
        children: [
            {
                path: AppRoutes.CHAT,
                component: ChatPage
            },
            {
                path: AppRoutes.SETTINGS,
                loadComponent: () => import('./features/settings/pages/settings-page.component').then(m => m.SettingsPage)
            },
            {
                path: AppRoutes.LIBRARY,
                loadComponent: () => import('./features/library/library.component').then(m => m.LibraryPageComponent)
            },
            {
                path: AppRoutes.COLLECTIONS,
                loadComponent: () => import('./features/collections/collections.component').then(m => m.CollectionsPageComponent)
            }
        ]
    }
];
