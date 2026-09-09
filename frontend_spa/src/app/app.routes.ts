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
                path: AppRoutes.SEARCH,
                loadComponent: () => import('./features/search/search.component').then(m => m.SearchComponent)
            },
            {
                path: AppRoutes.LIBRARY,
                loadComponent: () => import('./features/library/library.component').then(m => m.LibraryPageComponent)
            },
            {
                path: AppRoutes.COLLECTIONS,
                loadComponent: () => import('./features/collections/collections.component').then(m => m.CollectionsPageComponent)
            },
            {
                path: AppRoutes.REASONING,
                loadComponent: () => import('./pages/reasoning/reasoning.component').then(m => m.ReasoningComponent)
            },
            {
                path: AppRoutes.ABOUT,
                loadComponent: () => import('./features/about/pages/about.component').then(m => m.AboutComponent)
            },
            {
                path: AppRoutes.WIKI,
                loadComponent: () => import('./features/wiki/wiki-index.component').then(m => m.WikiIndexComponent)
            },
            {
                path: AppRoutes.WIKI + '/:name',
                loadComponent: () => import('./features/wiki/wiki-article.component').then(m => m.WikiArticleComponent)
            },
            {
                path: AppRoutes.VIDEOMIX,
                loadComponent: () => import('./features/videomix/pages/videomix-page.component').then(m => m.VideoMixPageComponent)
            },
            {
                path: AppRoutes.VIDEOMIX + '/:id',
                loadComponent: () => import('./features/videomix/pages/videomix-detail-page.component').then(m => m.VideoMixDetailPageComponent)
            }
        ]
    }
];
