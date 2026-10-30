import { Routes } from '@angular/router';
import { AccesoComponent } from './acceso.component';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    redirectTo: 'acceso',
  },
  {
    path: 'acceso',
    component: AccesoComponent,
    data: { label: 'Acceso' },
  },
  {
    path: '**',
    redirectTo: 'acceso',
  },
];