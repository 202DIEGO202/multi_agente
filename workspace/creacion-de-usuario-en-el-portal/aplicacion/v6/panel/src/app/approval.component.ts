import { Component, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { catchError, of } from 'rxjs';

@Component({
  selector: 'app-approval',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
    <div class="container mt-3">
      <h2>Aprobación de solicitud por líder de área</h2>

      <div *ngIf="errorMessage" class="alert alert-danger">{{ errorMessage }}</div>

      <div *ngIf="!token()">
        <p class="text-danger">Debe ingresar el token de administración para acceder.</p>
      </div>

      <ng-container *ngIf="token()">
        <ng-container *ngIf="loading()">Cargando solicitud...</ng-container>
        <ng-container *ngIf="!loading() && solicitud()">
          <section aria-label="Datos del solicitante" class="mb-3">
            <h3>Datos del solicitante</h3>
            <ul>
              <li>Nombre: {{ solicitud().nombres }}</li>
              <li>Cédula: {{ solicitud().cedula }}</li>
              <li>Área: {{ solicitud().area }}</li>
              <li>Cargo: {{ solicitud().cargo }}</li>
              <li>Fecha de nacimiento: {{ solicitud().fecha_nacimiento }}</li>
              <li>Edad: {{ solicitud().edad }} años</li>
              <li>Nivel de estudios: {{ solicitud().nivel_estudios }}</li>
            </ul>
          </section>

          <section aria-label="Datos del líder de área (aprobador)" class="mb-3">
            <h3>Datos del líder de área (aprobador)</h3>
            <ul>
              <li>Nombre: {{ solicitud().lider_area.nombres }}</li>
              <li>Cargo: {{ solicitud().lider_area.cargo }}</li>
              <li>Área: {{ solicitud().area }}</li>
              <li>Correo electrónico: {{ solicitud().lider_area.correo_electronico }}</li>
              <li>Fecha y hora de decisión: {{ fechaDecision() }}</li>
            </ul>
          </section>

          <section class="mb-3">
            <button class="btn btn-success me-2" (click)="aprobar()" [disabled]="decidiendo()">Aprobar solicitud</button>
            <button class="btn btn-danger me-2" (click)="rechazar()" [disabled]="decidiendo()">Rechazar solicitud</button>
          </section>

          <section class="mb-3">
            <label for="motivoRechazo">Motivo de rechazo (obligatorio si rechaza)</label>
            <textarea id="motivoRechazo" class="form-control" rows="3" [(ngModel)]="motivoRechazo" [disabled]="decidiendo()"></textarea>
          </section>

          <section aria-label="Estado de la aprobación" class="mb-3">
            <strong>Estado de la aprobación:</strong> {{ estado() }}
          </section>
        </ng-container>
      </ng-container>
    </div>
  `
})
export class ApprovalComponent {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private http = inject(HttpClient);

  token = signal<string | null>(sessionStorage.getItem('admin_token'));
  solicitud = signal<any | null>(null);
  loading = signal(false);
  errorMessage = '';
  motivoRechazo = '';
  decidiendo = signal(false);
  estado = signal('Pendiente');

  constructor() {
    this.loadSolicitud();
  }

  get solicitudId(): string | null {
    return this.route.snapshot.paramMap.get('id');
  }

  fechaDecision() {
    const fecha = this.solicitud()?.fecha_decision;
    return fecha ? new Date(fecha).toLocaleString() : '--/--/---- --:--';
  }

  loadSolicitud() {
    if (!this.token()) {
      this.errorMessage = 'Debe ingresar el token de administración para acceder.';
      return;
    }
    const id = this.solicitudId;
    if (!id) {
      this.errorMessage = 'ID de solicitud no especificado en la ruta.';
      return;
    }
    this.loading.set(true);
    this.errorMessage = '';
    this.http.get(`/api/admin/solicitudes/${id}`, {
      headers: { Authorization: `Bearer ${this.token()}` }
    }).pipe(
      catchError(err => {
        if (err.status === 401) {
          this.errorMessage = 'Token inválido o expirado. Por favor, ingrese el token nuevamente.';
          sessionStorage.removeItem('admin_token');
          this.token.set(null);
          this.solicitud.set(null);
          this.loading.set(false);
          return of(null);
        }
        this.errorMessage = 'Error al cargar la solicitud.';
        this.loading.set(false);
        return of(null);
      })
    ).subscribe(data => {
      if (data) {
        this.solicitud.set(data);
        this.estado.set(data.estado || 'Pendiente');
      }
      this.loading.set(false);
    });
  }

  aprobar() {
    if (!this.solicitud()) return;
    this.errorMessage = '';
    this.decidiendo.set(true);
    this.http.post(`/api/admin/solicitudes/${this.solicitud().id}/decidir`, { aprobar: true, motivo_rechazo: '' }, {
      headers: { Authorization: `Bearer ${this.token()}` }
    }).pipe(
      catchError(err => {
        this.errorMessage = err.error?.mensaje || 'Error al aprobar la solicitud.';
        this.decidiendo.set(false);
        return of(null);
      })
    ).subscribe(res => {
      if (res) {
        this.estado.set('Aprobada');
        this.solicitud().fecha_decision = new Date().toISOString();
      }
      this.decidiendo.set(false);
    });
  }

  rechazar() {
    if (!this.solicitud()) return;
    if (!this.motivoRechazo.trim()) {
      this.errorMessage = 'Motivo de rechazo es obligatorio si rechaza.';
      return;
    }
    this.errorMessage = '';
    this.decidiendo.set(true);
    this.http.post(`/api/admin/solicitudes/${this.solicitud().id}/decidir`, { aprobar: false, motivo_rechazo: this.motivoRechazo.trim() }, {
      headers: { Authorization: `Bearer ${this.token()}` }
    }).pipe(
      catchError(err => {
        this.errorMessage = err.error?.mensaje || 'Error al rechazar la solicitud.';
        this.decidiendo.set(false);
        return of(null);
      })
    ).subscribe(res => {
      if (res) {
        this.estado.set('Rechazada');
        this.solicitud().fecha_decision = new Date().toISOString();
        this.solicitud().motivo_rechazo = this.motivoRechazo.trim();
      }
      this.decidiendo.set(false);
    });
  }
}