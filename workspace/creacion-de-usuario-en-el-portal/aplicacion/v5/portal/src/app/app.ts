import { Component } from '@angular/core';
import { RouterModule, Routes, RouterOutlet } from '@angular/router';
import { SolicitudUsuarioComponent } from './solicitud-usuario.component';

export const routes: Routes = [
  { path: '', component: SolicitudUsuarioComponent },
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