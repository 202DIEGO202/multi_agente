import { Routes } from '@angular/router';
import { SolicitudesComponent } from './solicitudes';
import { NotificacionesComponent } from './notificaciones';

// Solo pantallas del empleado.
export const routes: Routes = [
  { path: '', component: SolicitudesComponent, data: { label: 'Solicitudes de ausencia' } },
  { path: 'notificaciones', component: NotificacionesComponent, data: { label: 'Notificaciones y detalle de solicitud' } }
];