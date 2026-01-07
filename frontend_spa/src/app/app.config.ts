import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideAnimations } from '@angular/platform-browser/animations';
import { provideToastr } from 'ngx-toastr';

import { provideHttpClient, withFetch } from '@angular/common/http';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(withFetch()),
    provideAnimations(), // required animations providers
    provideToastr({
      easing: 'ease-out',
      easeTime: 500,
      timeOut: 3500,
      positionClass: 'toast-bottom-right',
      preventDuplicates: true,
      closeButton: false, // minimalist/KISS
      progressBar: true,
      tapToDismiss: true,
      progressAnimation: 'decreasing',
      maxOpened: 5,
      // We will override these classes in styles.css
    }),
  ]
};
