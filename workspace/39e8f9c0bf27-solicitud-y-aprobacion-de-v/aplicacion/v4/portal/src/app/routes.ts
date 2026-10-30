import { Routes } from '@angular/router';
import { solicitudesAusenciaComponent } from './solicitudes-ausencia.component';
import { notificacionesDetalleSolicitudComponent } from './notificaciones-detalle-solicitud.component';
import { validacionTalentoHumanoComponent } from './validacion-talento-humano.component';
import { administracionTiposAusenciaComponent } from './administracion-tipos-ausencia.component';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'solicitudes-ausencia' },
  { path: 'solicitudes-ausencia', component: solicitudesAusenciaComponent, data: { label: 'Solicitudes de ausencia' } },
  { path: 'notificaciones-detalle-solicitud', component: notificacionesDetalleSolicitudComponent, data: { label: 'Notificaciones y detalle de solicitud' } },
  { path: 'validacion-talento-humano', component: validacionTalentoHumanoComponent, data: { label: 'Validación de Talento Humano' } },
  { path: 'administracion-tipos-ausencia', component: administracionTiposAusenciaComponent, data: { label: 'Administración de tipos de ausencia' } },
];