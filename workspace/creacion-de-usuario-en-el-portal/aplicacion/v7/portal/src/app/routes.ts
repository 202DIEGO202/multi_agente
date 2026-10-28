import { Routes } from '@angular/router';
import { SolicitudCreacionUsuarioComponent } from './solicitud-creacion-usuario.component';

export const routes: Routes = [
  {
    path: '',
    component: SolicitudCreacionUsuarioComponent,
    data: { label: 'Solicitud de creación de usuario corporativo' }
  }
];