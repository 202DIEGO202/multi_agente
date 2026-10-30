import { Routes } from '@angular/router';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { AdminApi } from './admin-api';
import { AccesoComponent } from './acceso';
import { JefeComponent } from './jefe';
import { TalentoHumanoComponent } from './talento-humano';
import { TiposAusenciaComponent } from './tipos-ausencia';

const autorizado = () => inject(AdminApi).authenticated() || inject(Router).createUrlTree(['/acceso']);

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'acceso' },
  { path: 'acceso', component: AccesoComponent, data: { label: 'Acceso administrativo' } },
  { path: 'jefe', component: JefeComponent, canActivate: [autorizado], data: { label: 'Bandeja de revisión - Jefe inmediato' } },
  { path: 'talento-humano', component: TalentoHumanoComponent, canActivate: [autorizado], data: { label: 'Validación de Talento Humano' } },
  { path: 'tipos-ausencia', component: TiposAusenciaComponent, canActivate: [autorizado], data: { label: 'Administración de tipos de ausencia' } }
];