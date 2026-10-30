import { Routes } from '@angular/router';
import { AccesoComponent } from './acceso.component';
import { BandejaRevisionComponent } from './bandeja-revision.component';

export const routes: Routes = [
  {
    path: '',
    component: AccesoComponent,
    data: { label: 'Acceso' },
  },
  {
    path: 'bandeja-revision',
    component: BandejaRevisionComponent,
    data: { label: 'Bandeja de revisión - Jefe inmediato' },
  },
];