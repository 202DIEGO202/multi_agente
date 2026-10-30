import { Routes } from '@angular/router';
import { SolicitudesComponent } from './solicitudes.component';
import { DetalleSolicitudComponent } from './detalle-solicitud.component';

export const routes: Routes = [
  { path: '', component: SolicitudesComponent, data: { label: 'Solicitudes de ausencia' } },
  { path: 'solicitudes/:id', component: DetalleSolicitudComponent }
];