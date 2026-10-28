import { Component } from '@angular/core';
import { RouterModule, Routes, RouterOutlet } from '@angular/router';
import { SolicitudFormComponent } from './solicitud-form.component';
import { AprobacionSolicitudComponent } from './aprobacion-solicitud.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: `
    <main>
      <router-outlet></router-outlet>
    </main>
  `
})
export class App {}

export const routes: Routes = [
  { path: '', component: SolicitudFormComponent },
  { path: 'aprobacion', component: AprobacionSolicitudComponent },
  { path: '**', redirectTo: '' }
];