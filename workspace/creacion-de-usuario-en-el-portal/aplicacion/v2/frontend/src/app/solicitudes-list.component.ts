import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';

@Component({
  selector: 'app-solicitudes-list',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <h2>Solicitudes de creación de usuario</h2>
    <table *ngIf="solicitudes.length > 0; else noData">
      <thead>
        <tr>
          <th>ID</th>
          <th>Cédula</th>
          <th>Nombres</th>
          <th>Estado</th>
          <th>Acciones</th>
        </tr>
      </thead>
      <tbody>
        <tr *ngFor="let s of solicitudes">
          <td>{{s.id}}</td>
          <td>{{s.cedula}}</td>
          <td>{{s.nombres}}</td>
          <td>
            <span [class.badge]="true" [class.success]="s.estado==='Aprobada'" [class.danger]="s.estado==='Rechazada'">
              {{s.estado}}
            </span>
          </td>
          <td class="actions">
            <button (click)="verDetalle(s.id)">Ver</button>
          </td>
        </tr>
      </tbody>
    </table>
    <ng-template #noData>
      <p>No hay solicitudes registradas.</p>
    </ng-template>
    <div *ngIf="error" class="error">{{error}}</div>
  `
})
export class SolicitudesListComponent implements OnInit {
  solicitudes: any[] = [];
  error = '';
  private router = inject(Router);

  ngOnInit() {
    this.cargarSolicitudes();
  }

  async cargarSolicitudes() {
    this.error = '';
    try {
      const res = await fetch('/api/solicitudes');
      if (!res.ok) {
        this.error = 'Error al cargar solicitudes.';
        return;
      }
      this.solicitudes = await res.json();
    } catch {
      this.error = 'Error de conexión al cargar solicitudes.';
    }
  }

  verDetalle(id: number) {
    this.router.navigate(['/solicitudes', id]);
  }
}