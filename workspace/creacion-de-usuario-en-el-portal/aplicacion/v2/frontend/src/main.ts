import { bootstrapApplication } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { App, routes } from './app/app';

bootstrapApplication(App, { providers: [provideRouter(routes), provideHttpClient()] }).catch(console.error);
