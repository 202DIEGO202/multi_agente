import { inject } from '@angular/core';
import { CanActivateFn, Routes } from '@angular/router';
import { AdminApi } from './admin-api';
import { AccesoComponent } from './acceso';
import { JefeComponent } from './jefe';
import { TalentoHumanoComponent } from './talento-humano';
import { TiposAusenciaComponent } from './tipos-ausencia';

const accesoAdministrativo: CanActivateFn = () => inject(AdminApi).guard();

export const routes: Routes = [
  { path: '', component: AccesoComponent, data: { label: 'Acceso' } },
  { path: 'revision-jefe', component: JefeComponent, canActivate: [accesoAdministrativo], data: { label: 'Bandeja de revisión - Jefe inmediato' } },
  { path: 'talento-humano', component: TalentoHumanoComponent, canActivate: [accesoAdministrativo], data: { label: 'Validación de Talento Humano' } },
  { path: 'tipos-ausencia', component: TiposAusenciaComponent, canActivate: [accesoAdministrativo], data: { label: 'Administración de tipos de ausencia' } }
];