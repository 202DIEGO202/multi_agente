import { Routes } from '@angular/router';
import { SolicitudesComponent } from './solicitudes';
import { NotificacionesComponent } from './notificaciones';
import { ValidacionComponent } from './validacion';
import { TiposAusenciaComponent } from './tipos-ausencia';

export const routes: Routes = [
  { path: '', component: SolicitudesComponent, data: { label: 'Solicitudes de ausencia' } },
  { path: 'notificaciones', component: NotificacionesComponent, data: { label: 'Notificaciones y detalle de solicitud' } },
  { path: 'validacion', component: ValidacionComponent, data: { label: 'Validación de Talento Humano' } },
  { path: 'tipos-ausencia', component: TiposAusenciaComponent, data: { label: 'Administración de tipos de ausencia' } }
];