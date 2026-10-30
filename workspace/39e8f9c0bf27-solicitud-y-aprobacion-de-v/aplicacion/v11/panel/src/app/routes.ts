import { inject } from '@angular/core';
import { CanActivateFn, Router, Routes } from '@angular/router';
import { AdminSession } from './admin-session';
import { Acceso } from './acceso';
import { BandejaRevision } from './bandeja-revision';
import { Validacion } from './validacion';

const requiereAcceso: CanActivateFn = () => {
  const session = inject(AdminSession);
  if (session.hasToken()) return true;
  session.message.set('Introduzca el Token de administración para acceder.');
  return inject(Router).createUrlTree(['/']);
};

export const routes: Routes = [
  { path: '', pathMatch: 'full', component: Acceso, data: { label: 'Acceso administrativo' } },
  {
    path: 'revision',
    component: BandejaRevision,
    canActivate: [requiereAcceso],
    data: { label: 'Bandeja de revisión - Jefe inmediato' }
  },
  {
    path: 'validacion',
    component: Validacion,
    canActivate: [requiereAcceso],
    data: { label: 'Validación de Talento Humano' }
  }
];