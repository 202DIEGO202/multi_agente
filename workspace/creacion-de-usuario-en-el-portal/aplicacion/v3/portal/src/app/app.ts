import { Component } from '@angular/core';
import { RouterModule, Routes, RouterOutlet } from '@angular/router';
import { SolicitudFormComponent } from './solicitud-form.component';
import { AprobacionSolicitudComponent } from './aprobacion-solicitud.component';

export const routes: Routes = [
  { path: '', component: SolicitudFormComponent },
  { path: 'aprobacion/:id', component: AprobacionSolicitudComponent },
  { path: '**', redirectTo: '' }
];

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterModule],
  template: `
    <main>
      <router-outlet></router-outlet>
    </main>
  `
})
export class App {
  // Raíz de la aplicación
}