import { Routes } from '@angular/router';
import { ApprovalComponent } from './approval.component';

export const routes: Routes = [
  {
    path: '',
    component: ApprovalComponent,
    data: { label: 'Aprobación de solicitud por líder de área' },
  },
];