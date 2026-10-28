import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { catchError, of } from 'rxjs';

interface Solicitud {
  id: number;
  cedula: string;
  nombres_completos: string;
  telefono: string;
  correo_electronico: string;
  fecha_nacimiento: string;
  edad: number;
  nivel_estudios: string;
  area: string;
  cargo: string;
  estado: string;
  fecha_envio: string;
  fecha_decision: string | null;
  lider_area: {
    id: number;
    nombre: string;
    correo_electronico: string;
    cargo: string;
    area: string;
  };
  motivo_rechazo: string | null;
}

@Component({
  selector: 'app-approval',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="container" *ngIf="solicitud() else noToken">
      <h1>Aprobación de solicitud por líder de área</h1>

      <section class="card">
        <h2>Datos del solicitante</h2>
        <p>Nombre: {{ solicitud().nombres_completos }}</p>
        <p>Cédula: {{ solicitud().cedula }}</p>
        <p>Área: {{ solicitud().area }}</p>
        <p>Cargo: {{ solicitud().cargo }}</p>
        <p>Fecha de nacimiento: {{ solicitud().fecha_nacimiento }}</p>
        <p>Edad: {{ solicitud().edad }} años</p>
        <p>Nivel de estudios: {{ solicitud().nivel_estudios }}</p>
      </section>

      <section class="card">
        <h2>Datos del líder de área (aprobador)</h2>
        <p>Nombre: {{ solicitud().lider_area.nombre }}</p>
        <p>Cargo: {{ solicitud().lider_area.cargo }}</p>
        <p>Área: {{ solicitud().lider_area.area }}</p>
        <p>Correo electrónico: {{ solicitud().lider_area.correo_electronico }}</p>
        <p>Fecha y hora de decisión: {{ solicitud().fecha_decision ?? '--/--/---- --:--' }}</p>
      </section>

      <section class="actions">
        <button class="btn btn-success" (click)="onApprove()" [disabled]="decisionMade()">Aprobar solicitud</button>
        <button class="btn btn-danger" (click)="onReject()" [disabled]="decisionMade()">Rechazar solicitud</button>
      </section>

      <section *ngIf="showRejectReason()" class="card">
        <label for="motivo">Motivo de rechazo (obligatorio si rechaza)</label>
        <textarea id="motivo" [(ngModel)]="motivoRechazo" rows="3" class="input"></textarea>
        <button class="btn btn-primary" (click)="submitRejection()" [disabled]="!motivoRechazo.trim()">Enviar rechazo</button>
        <button class="btn btn-secondary" (click)="cancelReject()">Cancelar</button>
      </section>

      <section *ngIf="estado()" class="status">
        <strong>Estado de la aprobación:</strong> {{ estado() }}
      </section>

      <p *ngIf="errorMessage()" class="error">{{ errorMessage() }}</p>
    </div>

    <ng-template #noToken>
      <p>No hay token de administración válido. <a routerLink="/">Volver al acceso</a></p>
    </ng-template>
  `,
})
export class ApprovalComponent {
  solicitud = signal<Solicitud | null>(null);
  estado = signal('');
  errorMessage = signal('');
  decisionMade = signal(false);
  showRejectReason = signal(false);
  motivoRechazo = '';

  private token = '';
  private solicitudId = '';

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private http: HttpClient
  ) {
    const storedToken = sessionStorage.getItem('admin_token');
    if (!storedToken) {
      this.router.navigate(['/']);
      return;
    }
    this.token = storedToken;

    this.solicitudId = this.route.snapshot.paramMap.get('id') || '';
    if (!this.solicitudId) {
      this.errorMessage.set('ID de solicitud no especificado');
      return;
    }

    this.loadSolicitud();
  }

  private headers() {
    return new HttpHeaders({
      Authorization: `Bearer ${this.token}`,
    });
  }

  private loadSolicitud() {
    this.http
      .get<Solicitud>(`/api/admin/solicitudes/${this.solicitudId}`, { headers: this.headers() })
      .pipe(
        catchError((err) => {
          if (err.status === 401) {
            sessionStorage.removeItem('admin_token');
            this.router.navigate(['/'], { state: { error: 'Token inválido o expirado. Por favor, ingrese nuevamente.' } });
          } else {
            this.errorMessage.set('Error al cargar la solicitud.');
          }
          return of(null);
        })
      )
      .subscribe((data) => {
        if (data) {
          this.solicitud.set(data);
          this.estado.set(data.estado);
          this.decisionMade.set(data.estado === 'Aprobada' || data.estado === 'Rechazada');
        }
      });
  }

  onApprove() {
    if (!this.solicitud()) return;
    this.errorMessage.set('');
    this.http
      .patch(
        `/api/admin/solicitudes/${this.solicitudId}/decidir`,
        { aprobar: true },
        { headers: this.headers() }
      )
      .pipe(
        catchError((err) => {
          if (err.status === 401) {
            sessionStorage.removeItem('admin_token');
            this.router.navigate(['/'], { state: { error: 'Token inválido o expirado. Por favor, ingrese nuevamente.' } });
          } else {
            this.errorMessage.set('Error al aprobar la solicitud.');
          }
          return of(null);
        })
      )
      .subscribe((res) => {
        if (res !== null) {
          this.estado.set('Aprobada');
          this.decisionMade.set(true);
          this.loadSolicitud();
        }
      });
  }

  onReject() {
    this.showRejectReason.set(true);
  }

  submitRejection() {
    if (!this.solicitud() || !this.motivoRechazo.trim()) return;
    this.errorMessage.set('');
    this.http
      .patch(
        `/api/admin/solicitudes/${this.solicitudId}/decidir`,
        { aprobar: false, motivo_rechazo: this.motivoRechazo.trim() },
        { headers: this.headers() }
      )
      .pipe(
        catchError((err) => {
          if (err.status === 401) {
            sessionStorage.removeItem('admin_token');
            this.router.navigate(['/'], { state: { error: 'Token inválido o expirado. Por favor, ingrese nuevamente.' } });
          } else {
            this.errorMessage.set('Error al rechazar la solicitud.');
          }
          return of(null);
        })
      )
      .subscribe((res) => {
        if (res !== null) {
          this.estado.set('Rechazada');
          this.decisionMade.set(true);
          this.showRejectReason.set(false);
          this.loadSolicitud();
        }
      });
  }

  cancelReject() {
    this.showRejectReason.set(false);
    this.motivoRechazo = '';
  }
}