import { Component, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

@Component({
  selector: 'app-approval',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="container mt-3" *ngIf="token() as token; else loginTemplate">
      <h2>Aprobación de solicitud por líder de área</h2>

      <div *ngIf="errorMessage()" class="alert alert-danger" role="alert">{{ errorMessage() }}</div>

      <div *ngIf="loading()" class="text-center my-3">Cargando solicitud...</div>

      <div *ngIf="!loading() && solicitud()">
        <section class="mb-3">
          <h3>Datos del solicitante</h3>
          <ul class="list-group">
            <li class="list-group-item">Nombre: {{ solicitud().nombres_completos }}</li>
            <li class="list-group-item">Cédula: {{ solicitud().cedula }}</li>
            <li class="list-group-item">Área: {{ solicitud().area }}</li>
            <li class="list-group-item">Cargo: {{ solicitud().cargo }}</li>
            <li class="list-group-item">Fecha de nacimiento: {{ solicitud().fecha_nacimiento | date:'dd/MM/yyyy' }}</li>
            <li class="list-group-item">Edad: {{ solicitud().edad }} años</li>
            <li class="list-group-item">Nivel de estudios: {{ solicitud().nivel_estudios }}</li>
          </ul>
        </section>

        <section class="mb-3">
          <h3>Datos del líder de área (aprobador)</h3>
          <ul class="list-group">
            <li class="list-group-item">Nombre: {{ solicitud().lider_area.nombre }}</li>
            <li class="list-group-item">Cargo: Líder de área</li>
            <li class="list-group-item">Área: {{ solicitud().area }}</li>
            <li class="list-group-item">Correo electrónico: {{ solicitud().lider_area.correo_electronico }}</li>
            <li class="list-group-item">Fecha y hora de decisión: {{ solicitud().fecha_decision ? (solicitud().fecha_decision | date:'dd/MM/yyyy HH:mm') : '--/--/---- --:--' }}</li>
          </ul>
        </section>

        <section class="mb-3">
          <label for="motivoRechazo" class="form-label">Motivo de rechazo (obligatorio si rechaza)</label>
          <textarea id="motivoRechazo" class="form-control" rows="3" [(ngModel)]="motivoRechazo" [disabled]="decision() === 'approved'"></textarea>
        </section>

        <section class="mb-3">
          <button class="btn btn-success me-2" (click)="decidir(true)" [disabled]="loadingDecision()">Aprobar solicitud</button>
          <button class="btn btn-danger" (click)="decidir(false)" [disabled]="loadingDecision()">Rechazar solicitud</button>
        </section>

        <section *ngIf="estadoDecision()" class="alert" [ngClass]="{'alert-success': estadoDecision() === 'Aprobada', 'alert-danger': estadoDecision() === 'Rechazada'}">
          Estado de la aprobación: {{ estadoDecision() }}
        </section>
      </div>
    </div>

    <ng-template #loginTemplate>
      <div class="container mt-3">
        <h2>Token de administración</h2>
        <div *ngIf="loginError()" class="alert alert-danger" role="alert">{{ loginError() }}</div>
        <form (ngSubmit)="guardarToken()" class="mb-3">
          <div class="mb-3">
            <label for="tokenInput" class="form-label">Token de administración</label>
            <input id="tokenInput" type="password" class="form-control" [(ngModel)]="tokenInput" name="tokenInput" required autocomplete="off" />
          </div>
          <button type="submit" class="btn btn-primary">Ingresar</button>
        </form>
      </div>
    </ng-template>
  `,
})
export class ApprovalComponent {
  private http = inject(HttpClient);
  private router = inject(Router);

  tokenInput = '';
  token = signal<string | null>(sessionStorage.getItem('admin_token'));
  loginError = signal('');

  solicitud = signal<any | null>(null);
  loading = signal(false);
  errorMessage = signal('');

  motivoRechazo = '';
  decision = signal<'approved' | 'rejected' | null>(null);
  estadoDecision = signal<string>('');
  loadingDecision = signal(false);

  constructor() {
    if (this.token()) {
      this.cargarSolicitud();
    }
  }

  guardarToken() {
    this.loginError.set('');
    if (!this.tokenInput.trim()) {
      this.loginError.set('El token es obligatorio');
      return;
    }
    sessionStorage.setItem('admin_token', this.tokenInput.trim());
    this.token.set(this.tokenInput.trim());
    this.tokenInput = '';
    this.cargarSolicitud();
  }

  cargarSolicitud() {
    this.loading.set(true);
    this.errorMessage.set('');
    this.solicitud.set(null);
    this.decision.set(null);
    this.estadoDecision.set('');
    this.motivoRechazo = '';

    const headers = new HttpHeaders({
      Authorization: `Bearer ${this.token()}`,
    });

    this.http
      .get<any[]>('/api/admin/solicitudes', { headers })
      .pipe(
        catchError((err) => {
          if (err.status === 401) {
            this.logout('Token inválido o expirado. Por favor, ingrese nuevamente.');
          } else {
            this.errorMessage.set('Error al cargar solicitudes.');
          }
          this.loading.set(false);
          return throwError(() => err);
        })
      )
      .subscribe((solicitudes) => {
        this.loading.set(false);
        if (!solicitudes || solicitudes.length === 0) {
          this.errorMessage.set('No hay solicitudes pendientes para aprobación.');
          this.solicitud.set(null);
          return;
        }
        const solicitudPendiente = solicitudes.find(s => s.estado === 'Pendiente');
        if (!solicitudPendiente) {
          this.errorMessage.set('No hay solicitudes pendientes para aprobación.');
          this.solicitud.set(null);
          return;
        }
        this.cargarDetalleSolicitud(solicitudPendiente.id);
      });
  }

  cargarDetalleSolicitud(id: number) {
    this.loading.set(true);
    const headers = new HttpHeaders({
      Authorization: `Bearer ${this.token()}`,
    });
    this.http
      .get<any>(`/api/admin/solicitudes/${id}`, { headers })
      .pipe(
        catchError((err) => {
          if (err.status === 401) {
            this.logout('Token inválido o expirado. Por favor, ingrese nuevamente.');
          } else {
            this.errorMessage.set('Error al cargar detalle de la solicitud.');
          }
          this.loading.set(false);
          return throwError(() => err);
        })
      )
      .subscribe((detalle) => {
        this.loading.set(false);
        this.solicitud.set(detalle);
        this.decision.set(null);
        this.estadoDecision.set('');
        this.motivoRechazo = '';
      });
  }

  decidir(aprobar: boolean) {
    if (!this.solicitud()) return;
    if (!aprobar && !this.motivoRechazo.trim()) {
      this.errorMessage.set('El motivo de rechazo es obligatorio si rechaza la solicitud.');
      return;
    }
    this.errorMessage.set('');
    this.loadingDecision.set(true);

    const headers = new HttpHeaders({
      Authorization: `Bearer ${this.token()}`,
      'Content-Type': 'application/json',
    });

    const body = {
      aprobar: aprobar,
      motivo_rechazo: aprobar ? null : this.motivoRechazo.trim(),
    };

    this.http
      .post(`/api/admin/solicitudes/${this.solicitud()!.id}/decidir`, body, { headers })
      .pipe(
        catchError((err) => {
          if (err.status === 401) {
            this.logout('Token inválido o expirado. Por favor, ingrese nuevamente.');
          } else if (err.error && err.error.mensaje) {
            this.errorMessage.set(err.error.mensaje);
          } else {
            this.errorMessage.set('Error al registrar la decisión.');
          }
          this.loadingDecision.set(false);
          return throwError(() => err);
        })
      )
      .subscribe(() => {
        this.loadingDecision.set(false);
        this.decision.set(aprobar ? 'approved' : 'rejected');
        this.estadoDecision.set(aprobar ? 'Aprobada' : 'Rechazada');
        const s = this.solicitud();
        if (s) {
          s.estado = aprobar ? 'Aprobada' : 'Rechazada';
          s.fecha_decision = new Date().toISOString();
          s.motivo_rechazo = aprobar ? null : this.motivoRechazo.trim();
          this.solicitud.set({ ...s });
        }
      });
  }

  logout(mensaje: string) {
    sessionStorage.removeItem('admin_token');
    this.token.set(null);
    this.solicitud.set(null);
    this.errorMessage.set('');
    this.loginError.set(mensaje);
  }
}