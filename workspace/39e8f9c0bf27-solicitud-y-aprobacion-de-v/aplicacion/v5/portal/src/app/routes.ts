import { Routes } from '@angular/router';
import { SolicitudesAusenciaComponent } from './solicitudes-ausencia.component';
import { NotificacionesDetalleSolicitudComponent } from './notificaciones-detalle-solicitud.component';
import { ValidacionTalentoHumanoComponent } from './validacion-talento-humano.component';
import { AdministracionTiposAusenciaComponent } from './administracion-tipos-ausencia.component';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'solicitudes-ausencia' },
  { path: 'solicitudes-ausencia', component: SolicitudesAusenciaComponent, data: { label: 'Solicitudes de ausencia' } },
  { path: 'notificaciones-detalle-solicitud', component: NotificacionesDetalleSolicitudComponent, data: { label: 'Notificaciones y detalle de solicitud' } },
  { path: 'validacion-talento-humano', component: ValidacionTalentoHumanoComponent, data: { label: 'Validación de Talento Humano' } },
  { path: 'administracion-tipos-ausencia', component: AdministracionTiposAusenciaComponent, data: { label: 'Administración de tipos de ausencia' } },
  { path: '**', redirectTo: 'solicitudes-ausencia' },
];