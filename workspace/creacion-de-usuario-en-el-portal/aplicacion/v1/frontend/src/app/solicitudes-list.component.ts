import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';

interface Estado {
  id: number;
  nombre: string;
}

interface Solicitud {
  id: number;
  usuario_id: number;
  fecha_envio: string;
  estado: Estado;
  nivel_estudios: string;
  fecha_nacimiento: string;
  cedula: string;
  nombres: string;
  telefono: string;
  correo_electronico: string;
}

@Component({
  selector: 'app-solicitudes-list',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <h2>Solicitudes de Creación de Usuario</h2>
    <table style="width:100%; border-collapse: collapse;">
      <thead>
        <tr style="background:#004d40; color:#fff;">
          <th style="padding:0.5rem; border:1px solid #ccc; text-align:left;">ID</th>
          <th style="padding:0.5rem; border:1px solid #ccc; text-align:left;">Nombres</th>
          <th style="padding:0.5rem; border:1px solid #ccc; text-align:left;">Cédula</th>
          <th style="padding:0.5rem; border:1px solid #ccc; text-align:left;">Estado</th>
          <th style="padding:0.5rem; border:1px solid #ccc; text-align:left;">Fecha Envío</th>
          <th style="padding:0.5rem; border:1px solid #ccc; text-align:left;">Acciones</th>
        </tr>
      </thead>
      <tbody>
        <tr *ngFor="let s of solicitudes" style="border:1px solid #ccc;">
          <td style="padding:0.5rem; border:1px solid #ccc;">{{s.id}}</td>
          <td style="padding:0.5rem; border:1px solid #ccc;">{{s.nombres}}</td>
          <td style="padding:0.5rem; border:1px solid #ccc;">{{s.cedula}}</td>
          <td style="padding:0.5rem; border:1px solid #ccc;">{{s.estado.nombre}}</td>
          <td style="padding:0.5rem; border:1px solid #ccc;">{{s.fecha_envio | date:'short'}}</td>
          <td style="padding:0.5rem; border:1px solid #ccc;">
            <button (click)="verDetalle(s.id)" style="padding:0.3rem 0.6rem;">Ver</button>
          </td>
        </tr>
        <tr *ngIf="solicitudes.length === 0">
          <td colspan="6" style="text-align:center; padding:1rem;">No hay solicitudes.</td>
        </tr>
      </tbody>
    </table>
    <div *ngIf="error" style="color:red; margin-top:1rem;">{{error}}</div>
  `
})
export class SolicitudesListComponent implements OnInit {
  solicitudes: Solicitud[] = [];
  error = '';

  constructor(private router: Router) {}

  ngOnInit(): void {
    this.cargarSolicitudes();
  }

  async cargarSolicitudes() {
    this.error = '';
    try {
      const res = await fetch('/api/solicitudes');
      if (!res.ok) {
        this.error = 'Error al cargar solicitudes';
        return;
      }
      this.solicitudes = await res.json();
    } catch {
      this.error = 'Error de conexión al cargar solicitudes';
    }
  }

  verDetalle(id: number) {
    this.router.navigate(['/solicitudes', id]);
  }
}