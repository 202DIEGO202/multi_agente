import { Component, importProvidersFrom, signal } from '@angular/core';
import { RouterModule, Routes, RouterOutlet } from '@angular/router';
import { SolicitudFormComponent } from './solicitud-form.component';

// Rutas de la aplicación portal
export const routes: Routes = [
  { path: '', component: SolicitudFormComponent },
  { path: '**', redirectTo: '' }
];

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterModule],
  template: `
    <main>
      <router-outlet></router-outlet>
    </main>
  `
})
export class App {
  // Raíz de la aplicación
}