import { Component, inject } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';
import { CommonModule } from '@angular/common';
import { SolicitudFormComponent } from './solicitud-form.component';
import { SolicitudesListComponent } from './solicitudes-list.component';
import { SolicitudDetalleComponent } from './solicitud-detalle.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <nav>
      <a routerLink="/solicitar" routerLinkActive="active" [routerLinkActiveOptions]="{exact:true}">Nueva Solicitud</a> |
      <a routerLink="/solicitudes" routerLinkActive="active">Solicitudes</a>
    </nav>
    <main>
      <router-outlet></router-outlet>
    </main>
  `
})
export class App {}

export const routes: Routes = [
  { path: '', redirectTo: 'solicitar', pathMatch: 'full' },
  { path: 'solicitar', component: SolicitudFormComponent },
  { path: 'solicitudes', component: SolicitudesListComponent },
  { path: 'solicitudes/:id', component: SolicitudDetalleComponent },
  { path: '**', redirectTo: 'solicitar' }
];