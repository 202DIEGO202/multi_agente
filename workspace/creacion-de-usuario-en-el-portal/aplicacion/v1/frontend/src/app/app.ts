import { Component } from '@angular/core';
import { Routes, RouterModule, RouterOutlet } from '@angular/router';
import { CommonModule } from '@angular/common';
import { SolicitudFormComponent } from './solicitud-form.component';
import { SolicitudesListComponent } from './solicitudes-list.component';
import { SolicitudDetalleComponent } from './solicitud-detalle.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterModule, RouterOutlet],
  template: `
    <nav style="background:#004d40; color:#fff; padding:1rem; display:flex; gap:1rem;">
      <a routerLink="/solicitud" routerLinkActive="active" style="color:#fff; text-decoration:none;">Nueva Solicitud</a>
      <a routerLink="/solicitudes" routerLinkActive="active" style="color:#fff; text-decoration:none;">Solicitudes</a>
    </nav>
    <main style="padding:1rem;">
      <router-outlet></router-outlet>
    </main>
  `
})
export class App {}

export const routes: Routes = [
  { path: '', redirectTo: 'solicitud', pathMatch: 'full' },
  { path: 'solicitud', component: SolicitudFormComponent },
  { path: 'solicitudes', component: SolicitudesListComponent },
  { path: 'solicitudes/:id', component: SolicitudDetalleComponent },
  { path: '**', redirectTo: 'solicitud' }
];