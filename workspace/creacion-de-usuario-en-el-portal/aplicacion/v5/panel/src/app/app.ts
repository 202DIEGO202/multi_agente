import { importProvidersFrom, signal } from '@angular/core';
import { provideRouter, Route } from '@angular/router';
import { HttpClientModule, HttpClient, HttpHeaders, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Component, effect } from '@angular/core';
import { catchError, throwError } from 'rxjs';

// Servicio para manejar token y llamadas API con autorización
class AdminApiService {
  private http = inject(HttpClient);
  private tokenSignal = signal<string | null>(sessionStorage.getItem('admin_token'));

  get token() {
    return this.tokenSignal();
  }

  set token(value: string | null) {
    if (value) {
      sessionStorage.setItem('admin_token', value);
    } else {
      sessionStorage.removeItem('admin_token');
    }
    this.tokenSignal.set(value);
  }

  // Método para hacer GET con Authorization
  get<T>(url: string) {
    if (!this.token) {
      return throwError(() => new Error('No autorizado'));
    }
    const headers = new HttpHeaders({
      Authorization: `Bearer ${this.token}`
    });
    return this.http.get<T>(url, { headers }).pipe(
      catchError((err: HttpErrorResponse) => {
        if (err.status === 401) {
          this.token = null; // borrar token y forzar login
        }
        return throwError(() => err);
      })
    );
  }

  // Método para POST con Authorization
  post<T>(url: string, body: any) {
    if (!this.token) {
      return throwError(() => new Error('No autorizado'));
    }
    const headers = new HttpHeaders({
      Authorization: `Bearer ${this.token}`
    });
    return this.http.post<T>(url, body, { headers }).pipe(
      catchError((err: HttpErrorResponse) => {
        if (err.status === 401) {
          this.token = null;
        }
        return throwError(() => err);
      })
    );
  }
}

// Componente de acceso con token
@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="container mt-4">
      <h2>Acceso administrativo</h2>
      <form (submit)="$event.preventDefault(); onSubmit()">
        <div class="mb-3">
          <label for="token" class="form-label">Token de administración</label>
          <input id="token" type="password" class="form-control" [(ngModel)]="token" name="token" autocomplete="off" />
        </div>
        <button type="submit" class="btn btn-primary">Ingresar</button>
      </form>
      <div *ngIf="errorMessage" class="alert alert-danger mt-3" role="alert">{{ errorMessage }}</div>
    </div>
  `
})
class LoginComponent {
  token = '';
  errorMessage = '';
  private api = new AdminApiService();

  onSubmit() {
    if (!this.token.trim()) {
      this.errorMessage = 'El token es obligatorio';
      return;
    }
    // Probar token con llamada a /api/admin/solicitudes
    this.api.token = this.token.trim();
    this.api.get('/api/admin/solicitudes').subscribe({
      next: () => {
        this.errorMessage = '';
        // Navegar a la pantalla principal
        window.history.pushState({}, '', '/panel');
        location.reload();
      },
      error: (err) => {
        this.errorMessage = 'Token inválido o expirado. Intente de nuevo.';
        this.api.token = null;
      }
    });
  }
}

// Componente para la pantalla PA-002: Aprobación de solicitud por líder de área
@Component({
  selector: 'app-aprobacion-solicitud',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="container mt-4" *ngIf="solicitudSignal() as solicitud; else noData">
      <h2>Aprobación de solicitud por líder de área</h2>

      <section class="mb-3">
        <h5>Datos del solicitante</h5>
        <ul class="list-group">
          <li class="list-group-item">Nombre: {{ solicitud.nombres }}</li>
          <li class="list-group-item">Cédula: {{ solicitud.cedula }}</li>
          <li class="list-group-item">Área: {{ solicitud.area }}</li>
          <li class="list-group-item">Cargo: {{ solicitud.cargo }}</li>
          <li class="list-group-item">Fecha de nacimiento: {{ solicitud.fecha_nacimiento }}</li>
          <li class="list-group-item">Edad: {{ solicitud.edad }} años</li>
          <li class="list-group-item">Nivel de estudios: {{ solicitud.nivel_estudios }}</li>
        </ul>
      </section>

      <section class="mb-3">
        <h5>Datos del líder de área (aprobador)</h5>
        <ul class="list-group">
          <li class="list-group-item">Nombre: {{ lider.nombres }}</li>
          <li class="list-group-item">Cargo: {{ lider.cargo }}</li>
          <li class="list-group-item">Área: {{ lider.area }}</li>
          <li class="list-group-item">Correo electrónico: {{ lider.correo_electronico }}</li>
          <li class="list-group-item">Fecha y hora de decisión: {{ fechaDecision || '--/--/---- --:--' }}</li>
        </ul>
      </section>

      <section class="mb-3">
        <button class="btn btn-success me-2" (click)="aprobar()" [disabled]="decidiendo">Aprobar solicitud</button>
        <button class="btn btn-danger me-2" (click)="rechazar()" [disabled]="decidiendo">Rechazar solicitud</button>
      </section>

      <section class="mb-3">
        <label for="motivoRechazo" class="form-label">Motivo de rechazo (obligatorio si rechaza)</label>
        <textarea id="motivoRechazo" class="form-control" rows="3" [(ngModel)]="motivoRechazo" [disabled]="decidiendo"></textarea>
      </section>

      <section *ngIf="estadoAprobacion" class="alert" [ngClass]="{'alert-success': estadoAprobacion === 'Aprobada', 'alert-danger': estadoAprobacion === 'Rechazada'}">
        Estado de la aprobación: {{ estadoAprobacion }}
      </section>

      <section *ngIf="errorMessage" class="alert alert-danger">
        {{ errorMessage }}
      </section>
    </div>

    <ng-template #noData>
      <div class="container mt-4">
        <p>No hay datos para mostrar. Por favor, inicie sesión con un token válido.</p>
      </div>
    </ng-template>
  `
})
class AprobacionSolicitudComponent {
  private api = new AdminApiService();
  solicitudSignal = signal<any | null>(null);
  lider = {
    nombres: '',
    cargo: 'Líder de área',
    area: '',
    correo_electronico: ''
  };
  fechaDecision: string | null = null;
  motivoRechazo = '';
  estadoAprobacion: 'Aprobada' | 'Rechazada' | '' = '';
  decidiendo = false;
  errorMessage = '';

  constructor() {
    this.cargarSolicitud();
  }

  cargarSolicitud() {
    // Para demo, se carga la primera solicitud de /api/admin/solicitudes
    this.api.get<any[]>('/api/admin/solicitudes').subscribe({
      next: (solicitudes) => {
        if (solicitudes.length === 0) {
          this.solicitudSignal.set(null);
          return;
        }
        const solicitud = solicitudes[0];
        this.solicitudSignal.set(solicitud);
        this.lider.nombres = solicitud.lider_area.nombres || '';
        this.lider.area = solicitud.area || '';
        this.lider.correo_electronico = solicitud.lider_area.correo_electronico || '';
        this.fechaDecision = solicitud.fecha_decision ? new Date(solicitud.fecha_decision).toLocaleString() : null;
        this.estadoAprobacion = solicitud.estado === 'Aprobada' || solicitud.estado === 'Rechazada' ? solicitud.estado : '';
      },
      error: (err) => {
        this.solicitudSignal.set(null);
        if (err.status === 401) {
          this.errorMessage = 'Token inválido o expirado. Por favor, ingrese nuevamente.';
        } else {
          this.errorMessage = 'Error al cargar la solicitud.';
        }
      }
    });
  }

  aprobar() {
    if (this.decidiendo) return;
    this.errorMessage = '';
    this.decidiendo = true;
    const solicitud = this.solicitudSignal();
    if (!solicitud) {
      this.errorMessage = 'No hay solicitud para aprobar.';
      this.decidiendo = false;
      return;
    }
    this.api.post(`/api/admin/solicitudes/${solicitud.id}/decidir`, { accion: 'Aprobar' }).subscribe({
      next: (res: any) => {
        this.estadoAprobacion = 'Aprobada';
        this.fechaDecision = new Date().toLocaleString();
        this.motivoRechazo = '';
        this.decidiendo = false;
      },
      error: (err) => {
        this.errorMessage = 'Error al aprobar la solicitud.';
        this.decidiendo = false;
      }
    });
  }

  rechazar() {
    if (this.decidiendo) return;
    this.errorMessage = '';
    if (!this.motivoRechazo.trim()) {
      this.errorMessage = 'El motivo de rechazo es obligatorio si rechaza.';
      return;
    }
    this.decidiendo = true;
    const solicitud = this.solicitudSignal();
    if (!solicitud) {
      this.errorMessage = 'No hay solicitud para rechazar.';
      this.decidiendo = false;
      return;
    }
    this.api.post(`/api/admin/solicitudes/${solicitud.id}/decidir`, { accion: 'Rechazar', motivo_rechazo: this.motivoRechazo.trim() }).subscribe({
      next: (res: any) => {
        this.estadoAprobacion = 'Rechazada';
        this.fechaDecision = new Date().toLocaleString();
        this.decidiendo = false;
      },
      error: (err) => {
        this.errorMessage = 'Error al rechazar la solicitud.';
        this.decidiendo = false;
      }
    });
  }
}

// Componente raíz que decide mostrar login o panel
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, LoginComponent, AprobacionSolicitudComponent],
  template: `
    <ng-container *ngIf="token; else login">
      <app-aprobacion-solicitud></app-aprobacion-solicitud>
    </ng-container>
    <ng-template #login>
      <app-login></app-login>
    </ng-template>
  `
})
export class App {
  token = signal<string | null>(sessionStorage.getItem('admin_token'));

  constructor() {
    // Escuchar cambios en sessionStorage para token
    window.addEventListener('storage', (event) => {
      if (event.key === 'admin_token') {
        this.token.set(event.newValue);
      }
    });
  }
}

// Rutas para la aplicación panel
export const routes: Route[] = [
  { path: '', component: App }
];

// Proveedores para el módulo raíz
export const appProviders = [
  importProvidersFrom(HttpClientModule),
  provideRouter(routes)
];