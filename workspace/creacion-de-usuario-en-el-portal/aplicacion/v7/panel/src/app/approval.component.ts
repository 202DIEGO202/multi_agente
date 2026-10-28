import { Component, signal, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpHeaders, HttpErrorResponse } from '@angular/common/http';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

interface DatosSolicitante {
  nombres_completos: string;
  cedula: string;
  area: string;
  cargo: string;
  fecha_nacimiento: string; // YYYY-MM-DD
  edad: number;
  nivel_estudios: string;
}

interface DatosLider {
  nombres_completos: string;
  cargo: string;
  area: string;
  correo_electronico: string;
  fecha_hora_decision: string; // ISO string or '--/--/---- --:--'
}

interface Solicitud {
  id: number;
  datos_solicitante: DatosSolicitante;
  datos_lider: DatosLider;
  estado: string;
  motivo_rechazo: string;
}

@Component({
  selector: 'app-approval',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
  <div class="container mt-3">
    <h2>Aprobación de solicitud por líder de área</h2>

    <div *ngIf="!token()" class="alert alert-warning">
      <label for="tokenInput">Token de administración:</label>
      <input id="tokenInput" type="password" [(ngModel)]="tokenInput" class="form-control" (keyup.enter)="guardarToken()" />
      <button class="btn btn-primary mt-2" (click)="guardarToken()">Ingresar</button>
      <div *ngIf="mensajeError()" class="text-danger mt-2">{{ mensajeError() }}</div>
    </div>

    <div *ngIf="token()">
      <div *ngIf="mensajeError()" class="alert alert-danger">{{ mensajeError() }}</div>

      <div *ngIf="!solicitud() && !cargando()" class="alert alert-info">Cargando solicitud...</div>
      <div *ngIf="cargando()" class="alert alert-info">Cargando solicitud...</div>

      <div *ngIf="solicitud()">
        <section class="mb-3">
          <h4>Datos del solicitante</h4>
          <ul class="list-group">
            <li class="list-group-item">Nombre: {{ solicitud().datos_solicitante.nombres_completos }}</li>
            <li class="list-group-item">Cédula: {{ solicitud().datos_solicitante.cedula }}</li>
            <li class="list-group-item">Área: {{ solicitud().datos_solicitante.area }}</li>
            <li class="list-group-item">Cargo: {{ solicitud().datos_solicitante.cargo }}</li>
            <li class="list-group-item">Fecha de nacimiento: {{ solicitud().datos_solicitante.fecha_nacimiento }}</li>
            <li class="list-group-item">Edad: {{ solicitud().datos_solicitante.edad }} años</li>
            <li class="list-group-item">Nivel de estudios: {{ solicitud().datos_solicitante.nivel_estudios }}</li>
          </ul>
        </section>

        <section class="mb-3">
          <h4>Datos del líder de área (aprobador)</h4>
          <ul class="list-group">
            <li class="list-group-item">Nombre: {{ solicitud().datos_lider.nombres_completos }}</li>
            <li class="list-group-item">Cargo: {{ solicitud().datos_lider.cargo }}</li>
            <li class="list-group-item">Área: {{ solicitud().datos_lider.area }}</li>
            <li class="list-group-item">Correo electrónico: {{ solicitud().datos_lider.correo_electronico }}</li>
            <li class="list-group-item">Fecha y hora de decisión: {{ solicitud().datos_lider.fecha_hora_decision || '--/--/---- --:--' }}</li>
          </ul>
        </section>

        <section class="mb-3">
          <label for="motivoRechazo">Motivo de rechazo (obligatorio si rechaza):</label>
          <textarea id="motivoRechazo" class="form-control" [(ngModel)]="motivoRechazo" rows="3" [disabled]="aprobando()" placeholder="Ingrese motivo si rechaza"></textarea>
        </section>

        <section class="mb-3">
          <button class="btn btn-success me-2" (click)="aprobar()" [disabled]="aprobando()">Aprobar solicitud</button>
          <button class="btn btn-danger" (click)="rechazar()" [disabled]="aprobando()">Rechazar solicitud</button>
        </section>

        <section *ngIf="estadoDecision()" class="alert alert-info">
          Estado de la aprobación: {{ estadoDecision() }}
        </section>
      </div>
    </div>
  </div>
  `,
})
export class ApprovalComponent {
  tokenInput = '';
  private _token = signal<string | null>(sessionStorage.getItem('admin_token'));
  token = this._token.asReadonly();

  solicitud = signal<Solicitud | null>(null);
  mensajeError = signal('');
  motivoRechazo = '';
  estadoDecision = signal('');
  cargando = signal(false);
  aprobando = signal(false);

  constructor(private http: HttpClient, private router: Router) {
    if (this.token()) {
      this.cargarSolicitud();
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

  guardarToken() {
    if (this.tokenInput.trim()) {
      this._token.set(this.tokenInput.trim());
      this.mensajeError.set('');
      this.cargarSolicitud();
    }
  }

  private headers() {
    return new HttpHeaders({
      Authorization: `Bearer ${this.token()}`,
    });
  }

  private cargarSolicitud() {
    this.cargando.set(true);
    this.mensajeError.set('');
    this.estadoDecision.set('');
    this.solicitud.set(null);

    // Carga la primera solicitud pendiente para aprobación
    this.http
      .get<Solicitud[]>('/api/admin/solicitudes', { headers: this.headers() })
      .pipe(
        catchError((error: HttpErrorResponse) => {
          if (error.status === 401) {
            this.mensajeError.set('Token inválido o expirado. Por favor ingrese un token válido.');
            this._token.set(null);
            this.cargando.set(false);
            return throwError(() => error);
          }
          this.mensajeError.set('Error al cargar solicitudes.');
          this.cargando.set(false);
          return throwError(() => error);
        })
      )
      .subscribe((solicitudes) => {
        if (solicitudes.length > 0) {
          this.solicitud.set(solicitudes[0]);
        } else {
          this.mensajeError.set('No hay solicitudes pendientes para aprobación.');
          this.solicitud.set(null);
        }
        this.cargando.set(false);
      });
  }

  aprobar() {
    if (!this.solicitud()) return;
    this.aprobando.set(true);
    this.mensajeError.set('');
    this.estadoDecision.set('');

    const body = { aprobar: true, motivo_rechazo: '' };

    this.http
      .post<{ id: number; estado: string }>(
        `/api/admin/solicitudes/${this.solicitud()!.id}/decidir`,
        body,
        { headers: this.headers() }
      )
      .pipe(
        catchError((error: HttpErrorResponse) => {
          if (error.status === 401) {
            this.mensajeError.set('Token inválido o expirado. Por favor ingrese un token válido.');
            this._token.set(null);
            this.aprobando.set(false);
            return throwError(() => error);
          }
          this.mensajeError.set('Error al aprobar la solicitud.');
          this.aprobando.set(false);
          return throwError(() => error);
        })
      )
      .subscribe((res) => {
        this.estadoDecision.set(res.estado);
        this.aprobando.set(false);
        this.cargarSolicitud();
        this.motivoRechazo = '';
      });
  }

  rechazar() {
    if (!this.solicitud()) return;
    if (!this.motivoRechazo.trim()) {
      this.mensajeError.set('El motivo de rechazo es obligatorio.');
      return;
    }
    this.aprobando.set(true);
    this.mensajeError.set('');
    this.estadoDecision.set('');

    const body = { aprobar: false, motivo_rechazo: this.motivoRechazo.trim() };

    this.http
      .post<{ id: number; estado: string }>(
        `/api/admin/solicitudes/${this.solicitud()!.id}/decidir`,
        body,
        { headers: this.headers() }
      )
      .pipe(
        catchError((error: HttpErrorResponse) => {
          if (error.status === 401) {
            this.mensajeError.set('Token inválido o expirado. Por favor ingrese un token válido.');
            this._token.set(null);
            this.aprobando.set(false);
            return throwError(() => error);
          }
          this.mensajeError.set('Error al rechazar la solicitud.');
          this.aprobando.set(false);
          return throwError(() => error);
        })
      )
      .subscribe((res) => {
        this.estadoDecision.set(res.estado);
        this.aprobando.set(false);
        this.cargarSolicitud();
        this.motivoRechazo = '';
      });
  }
}