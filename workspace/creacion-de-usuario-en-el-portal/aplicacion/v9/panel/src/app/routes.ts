import { Routes } from '@angular/router';
import { ApprovalComponent } from './approval.component';
import { AccessComponent } from './access.component';

export const routes: Routes = [
  { path: '', component: AccessComponent, data: { label: 'Acceso administrativo' } },
  { path: 'approval/:id', component: ApprovalComponent, data: { label: 'Aprobación de solicitud por líder de área' } },
];