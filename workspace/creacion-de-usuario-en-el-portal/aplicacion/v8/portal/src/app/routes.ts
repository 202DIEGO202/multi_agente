import { Routes } from '@angular/router';
import { SolicitudComponent } from './solicitud.component';

export const routes: Routes = [
  { path: '', component: SolicitudComponent, data: { label: 'Solicitud de creación de usuario corporativo' } },
];