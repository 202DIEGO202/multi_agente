import { inject } from '@angular/core';
import { CanActivateFn, Router, Routes } from '@angular/router';
import { AdminApi } from './admin-api';
import { AccesoComponent } from './acceso';
import { JefeComponent } from './jefe';
import { TalentoHumanoComponent } from './talento-humano';
import { TiposAusenciaComponent } from './tipos-ausencia';

const autenticado: CanActivateFn = () => {
  const api = inject(AdminApi);
  if (api.tieneToken()) return true;
  api.mensajeAcceso.set('Introduce un token de administración para acceder.');
  return inject(Router).createUrlTree(['/']);
};

export const routes: Routes = [
  { path: '', pathMatch: 'full', component: AccesoComponent, data: { label: 'Acceso' } },
  { path: 'revision-jefe', component: JefeComponent, canActivate: [autenticado], data: { label: 'Bandeja de revisión - Jefe inmediato' } },
  { path: 'talento-humano', component: TalentoHumanoComponent, canActivate: [autenticado], data: { label: 'Validación de Talento Humano' } },
  { path: 'tipos-ausencia', component: TiposAusenciaComponent, canActivate: [autenticado], data: { label: 'Administración de tipos de ausencia' } }
];