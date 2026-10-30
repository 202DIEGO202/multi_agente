import { Routes } from '@angular/router';
import { NotificacionesDetalleComponent } from './notificaciones-detalle.component';
import { SolicitudesAusenciaComponent } from './solicitudes-ausencia.component';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'solicitudes' },
  { path: 'solicitudes', component: SolicitudesAusenciaComponent, data: { label: 'Solicitudes de ausencia' } },
  { path: 'detalle', component: NotificacionesDetalleComponent, data: { label: 'Notificaciones y detalle de solicitud' } },
];