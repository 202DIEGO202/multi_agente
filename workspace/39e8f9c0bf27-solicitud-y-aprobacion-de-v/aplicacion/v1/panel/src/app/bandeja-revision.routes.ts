import { Routes } from '@angular/router';
import { BandejaRevisionComponent } from './bandeja-revision.component';

export const bandejaRevisionRoutes: Routes = [
  {
    path: 'bandeja-revision',
    component: BandejaRevisionComponent,
    data: { label: 'Bandeja de revisión - Jefe inmediato' },
  },
];