import { Routes } from '@angular/router';
import { adminGuard } from './shared/admin.guard';
import { accesoComponent } from './acceso.component';
import { bandejaRevisionComponent } from './bandeja-revision.component';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'acceso' },
  { path: 'acceso', component: accesoComponent, data: { label: 'Acceso' } },
  {
    path: 'bandeja-revision',
    component: bandejaRevisionComponent,
    canActivate: [adminGuard],
    data: { label: 'Bandeja de revisión - Jefe inmediato' },
  },
  { path: '**', redirectTo: 'acceso' },
];