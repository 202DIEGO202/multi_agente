import { Component, signal, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpHeaders, HttpErrorResponse } from '@angular/common/http';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

interface Solicitud {
  id: number;
  cedula: string;
  nombres: string;
  telefono: string;
  correo_electronico: string;
  fecha_nacimiento: string;
  edad: number;
  nivel_estudios: string;
  estado: string;
  fecha_envio: string;
  fecha_decision: string | null;
  motivo_rechazo: string | null;
  lider_area: {
    id: number;
    nombres: string;
    cargo: string;
    area_id: number;
    correo_electronico: string;
  };
  aprobador?: {
    nombre: string;
    cargo: string;
    area_id: number;
    correo_electronico: string;
    fecha_decision: string;
  };
}

@Component({
  selector: 'app-approval',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
  <div class="container mt-3">
    <h2>Aprobación de solicitud por líder de área</h2>

    <div *ngIf="!token()" class="mt-4">
      <label for="tokenInput" class="form-label">Token de administración</label>
      <input id="tokenInput" type="password" class="form-control" [(ngModel)]="tokenInput" (keyup.enter)="saveToken()" placeholder="Ingrese token" />
      <button class="btn btn-primary mt-2" (click)="saveToken()">Acceder</button>
      <div *ngIf="errorMessage()" class="alert alert-danger mt-2">{{ errorMessage() }}</div>
    </div>

    <div *ngIf="token()" class="mt-4">
      <div *ngIf="loading()" class="alert alert-info">Cargando solicitud...</div>
      <div *ngIf="errorMessage() && !loading()" class="alert alert-danger">{{ errorMessage() }}</div>

      <ng-container *ngIf="solicitud()">
        <div class="card mb-3">
          <div class="card-header">Datos del solicitante</div>
          <div class="card-body">
            <p>Nombre: {{ solicitud().nombres }}</p>
            <p>Cédula: {{ solicitud().cedula }}</p>
            <p>Área: {{ solicitud().lider_area ? solicitud().lider_area.area_id : 'N/A' }}</p>
            <p>Cargo: {{ solicitud().lider_area ? solicitud().lider_area.cargo : 'N/A' }}</p>
            <p>Fecha de nacimiento: {{ solicitud().fecha_nacimiento }}</p>
            <p>Edad: {{ solicitud().edad }} años</p>
            <p>Nivel de estudios: {{ solicitud().nivel_estudios }}</p>
          </div>
        </div>

        <div class="card mb-3">
          <div class="card-header">Datos del líder de área (aprobador)</div>
          <div class="card-body">
            <p>Nombre: {{ aprobador().nombre }}</p>
            <p>Cargo: {{ aprobador().cargo }}</p>
            <p>Área: {{ aprobador().area_id }}</p>
            <p>Correo electrónico: {{ aprobador().correo_electronico }}</p>
            <p>Fecha y hora de decisión: {{ aprobador().fecha_decision || '--/--/---- --:--' }}</p>
          </div>
        </div>

        <div class="mb-3">
          <button class="btn btn-success me-2" (click)="decidir('Aprobar')" [disabled]="decidiendo() || solicitud().estado !== 'Pendiente'">Aprobar solicitud</button>
          <button class="btn btn-danger me-2" (click)="rechazarVisible.set(true)" [disabled]="decidiendo() || solicitud().estado !== 'Pendiente'">Rechazar solicitud</button>
        </div>

        <div *ngIf="rechazarVisible()" class="mb-3">
          <label for="motivoRechazo" class="form-label">Motivo de rechazo (obligatorio si rechaza)</label>
          <textarea id="motivoRechazo" class="form-control" [(ngModel)]="motivoRechazo" rows="3"></textarea>
          <button class="btn btn-danger mt-2" (click)="decidir('Rechazar')" [disabled]="!motivoRechazo.trim() || decidiendo()">Confirmar rechazo</button>
          <button class="btn btn-secondary mt-2 ms-2" (click)="cancelarRechazo()" [disabled]="decidiendo()">Cancelar</button>
        </div>

        <div *ngIf="estadoDecision()" class="alert alert-info">Estado de la aprobación: {{ estadoDecision() }}</div>
      </ng-container>
    </div>
  </div>
  `,
})
export class ApprovalComponent {
  tokenInput = '';
  private _token = signal<string | null>(sessionStorage.getItem('admin_token'));
  token = this._token.asReadonly();

  solicitud = signal<Solicitud | null>(null);
  aprobador = signal<{ nombre: string; cargo: string; area_id: number; correo_electronico: string; fecha_decision: string | null }>({
    nombre: '',
    cargo: '',
    area_id: 0,
    correo_electronico: '',
    fecha_decision: null,
  });
  errorMessage = signal('');
  loading = signal(false);
  decidiendo = signal(false);
  motivoRechazo = '';
  rechazarVisible = signal(false);
  estadoDecision = signal('');

  constructor(private http: HttpClient, private router: Router) {
    // Si ya hay token, cargar solicitud
    if (this.token()) {
      this.loadSolicitud();
    }

    // Efecto para guardar token en sessionStorage
    effect(() => {
      const t = this.token();
      if (t) {
        sessionStorage.setItem('admin_token', t);
      } else {
        sessionStorage.removeItem('admin_token');
      }
    });
  }

  saveToken() {
    if (this.tokenInput.trim()) {
      this._token.set(this.tokenInput.trim());
      this.errorMessage.set('');
      this.loadSolicitud();
    }
  }

  loadSolicitud() {
    this.loading.set(true);
    this.errorMessage.set('');
    this.solicitud.set(null);
    this.estadoDecision.set('');
    this.rechazarVisible.set(false);
    this.motivoRechazo = '';

    const headers = new HttpHeaders({
      Authorization: `Bearer ${this.token()}`,
    });

    // Cargar la primera solicitud pendiente para aprobación
    this.http
      .get<Solicitud[]>('/api/admin/solicitudes', { headers })
      .pipe(
        catchError((error: HttpErrorResponse) => {
          if (error.status === 401) {
            this.errorMessage.set('Token inválido o expirado. Por favor, ingrese un token válido.');
            this._token.set(null);
            this.loading.set(false);
            return throwError(() => error);
          }
          this.errorMessage.set('Error al cargar solicitudes.');
          this.loading.set(false);
          return throwError(() => error);
        })
      )
      .subscribe((solicitudes) => {
        if (solicitudes.length === 0) {
          this.errorMessage.set('No hay solicitudes pendientes para aprobación.');
          this.loading.set(false);
          return;
        }
        const solicitud = solicitudes[0];
        this.solicitud.set(solicitud);

        // Set aprobador info from lider_area (simulate current user)
        this.aprobador.set({
          nombre: 'Laura Gómez',
          cargo: 'Líder de área',
          area_id: solicitud.lider_area.area_id,
          correo_electronico: solicitud.lider_area.correo_electronico,
          fecha_decision: null,
        });

        this.loading.set(false);
      });
  }

  decidir(accion: 'Aprobar' | 'Rechazar') {
    if (!this.solicitud()) return;
    if (accion === 'Rechazar' && !this.motivoRechazo.trim()) {
      this.errorMessage.set('El motivo de rechazo es obligatorio.');
      return;
    }

    this.decidiendo.set(true);
    this.errorMessage.set('');

    const headers = new HttpHeaders({
      Authorization: `Bearer ${this.token()}`,
      'Content-Type': 'application/json',
    });

    const body = {
      accion: accion,
      motivo_rechazo: accion === 'Rechazar' ? this.motivoRechazo.trim() : '',
    };

    this.http
      .post<{ mensaje: string }>(`/api/admin/solicitudes/${this.solicitud()!.id}/decidir`, body, { headers })
      .pipe(
        catchError((error: HttpErrorResponse) => {
          if (error.status === 401) {
            this.errorMessage.set('Token inválido o expirado. Por favor, ingrese un token válido.');
            this._token.set(null);
            this.decidiendo.set(false);
            return throwError(() => error);
          }
          this.errorMessage.set('Error al enviar la decisión.');
          this.decidiendo.set(false);
          return throwError(() => error);
        })
      )
      .subscribe((res) => {
        this.estadoDecision.set(`Solicitud ${accion.toLowerCase()}ada correctamente.`);
        // Actualizar estado local
        this.solicitud.update((s) => {
          if (!s) return s;
          s.estado = accion === 'Aprobar' ? 'Aprobada' : 'Rechazada';
          s.motivo_rechazo = accion === 'Rechazar' ? this.motivoRechazo.trim() : null;
          s.fecha_decision = new Date().toISOString();
          return s;
        });
        // Actualizar fecha_decision en aprobador
        this.aprobador.update((a) => {
          a.fecha_decision = new Date().toLocaleString();
          return a;
        });
        this.decidiendo.set(false);
        this.rechazarVisible.set(false);
        this.motivoRechazo = '';
      });
  }

  cancelarRechazo() {
    this.rechazarVisible.set(false);
    this.motivoRechazo = '';
    this.errorMessage.set('');
  }
}