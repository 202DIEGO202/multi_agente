import { inject } from '@angular/core';
import { CanActivateFn, Routes, Router } from '@angular/router';
import { AccesoComponent } from './acceso';
import { SolicitudesComponent } from './solicitudes';
import { DetalleComponent } from './detalle';
import { PortalApi } from './portal-api';

const accesoRequerido: CanActivateFn = () => inject(PortalApi).tieneSesion() || inject(Router).createUrlTree(['/acceso']);

export const routes: Routes = [
  { path: 'acceso', component: AccesoComponent, data: { label: 'Acceso' } },
  { path: '', component: SolicitudesComponent, canActivate: [accesoRequerido], data: { label: 'Solicitudes de ausencia' } },
  { path: 'solicitudes/:id', component: DetalleComponent, canActivate: [accesoRequerido] }
];