import { Routes } from '@angular/router';
import { AccesoComponent } from './acceso.component';
import { SolicitudesPendientesComponent } from './solicitudes-pendientes.component';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'acceso' },
  { path: 'acceso', component: AccesoComponent, data: { label: 'Acceso' } },
  { path: 'solicitudes-pendientes', component: SolicitudesPendientesComponent, data: { label: 'Bandeja de revisión - Jefe inmediato' } },
  { path: '**', redirectTo: 'acceso' },
];