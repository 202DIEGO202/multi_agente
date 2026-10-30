import { Routes } from '@angular/router';
import { AccesoComponent } from './acceso.component';

export const accesoRoutes: Routes = [
  {
    path: '',
    component: AccesoComponent,
    data: { label: 'Acceso' },
  },
];