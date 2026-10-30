import { CommonModule } from '@angular/common';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

interface Solicitud {
  id: number;
  solicitante_nombre: string;
  solicitante_documento?: string;
  area?: string;
  tipo_ausencia_id?: number;
  fecha_inicio: string;
  fecha_fin: string;
  estado_codigo: string;
  version?: number;
}

@Component({
  selector: 'app-bandeja-revision',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="p-4">
      <h1>Bandeja de revisión - Jefe inmediato</h1>

      <p *ngIf="error()" class="mt-3">{{ error() }}</p>
      <p *ngIf="mensaje()" class="mt-3">{{ mensaje() }}</p>

      <div class="mt-4">
        <button type="button" (click)="cargar()">Actualizar solicitudes pendientes</button>
      </div>

      <div class="mt-4">
        <h2>Solicitudes pendientes</h2>
        <ul>
          <li *ngFor="let s of solicitudes()" (click)="seleccionar(s)">
            Solicitante: {{ s.solicitante_nombre }} | Tipo: {{ s.tipo_ausencia_id || 'Sin dato' }} | Fechas: {{ s.fecha_inicio }} - {{ s.fecha_fin }}
          </li>
        </ul>
      </div>

      <div class="mt-4" *ngIf="seleccionada() as s">
        <h2>Solicitud en revisión</h2>
        <p>Solicitante: {{ s.solicitante_nombre }}</p>
        <p>Área: {{ s.area || 'Sin dato' }}</p>
        <p>Tipo de ausencia: {{ s.tipo_ausencia_id || 'Sin dato' }}</p>
        <p>Fechas: {{ s.fecha_inicio }} - {{ s.fecha_fin }}</p>
        <p>Observación del empleado: Viaje familiar</p>

        <label class="block mt-3" for="obs">Observaciones de revisión del jefe</label>
        <textarea id="obs" name="obs" [(ngModel)]="observacion" class="w-full"></textarea>

        <div class="mt-3">
          <button type="button" (click)="decidir('aprobar')">Aprobar solicitud</button>
          <button type="button" (click)="decidir('rechazar')" class="ml-2">Rechazar solicitud</button>
        </div>
      </div>
    </section>
  `,
})
export class BandejaRevisionComponent {
  private readonly http = inject(HttpClient);
  private readonly _solicitudes = signal<Solicitud[]>([]);
  solicitudes = computed(() => this._solicitudes());
  private readonly _seleccionada = signal<Solicitud | null>(null);
  seleccionada = computed(() => this._seleccionada());
  observacion = '';
  private readonly _mensaje = signal('');
  mensaje = computed(() => this._mensaje());
  private readonly _error = signal('');
  error = computed(() => this._error());

  cargar(): void {
    this._mensaje.set('');
    this._error.set('');
    const token = sessionStorage.getItem('admin_token');
    if (!token) {
      this._error.set('Token de administración requerido.');
      return;
    }
    this.http.get<Solicitud[]>('/api/admin/solicitudes', { headers: this.authHeaders(token) }).subscribe({
      next: data => this._solicitudes.set(data),
      error: err => this.handleError(err),
    });
  }

  seleccionar(s: Solicitud): void {
    this._seleccionada.set(s);
  }

  decidir(accion: 'aprobar' | 'rechazar'): void {
    const s = this._seleccionada();
    const token = sessionStorage.getItem('admin_token');
    if (!s || !token) return;
    const url = `/api/admin/solicitudes/${s.id}/${accion}`;
    this.http.post(url, { observacion: this.observacion, usuario: 'admin', rol: 'ADMINISTRADOR' }, { headers: this.authHeaders(token) }).subscribe({
      next: () => {
        this._mensaje.set(accion === 'aprobar' ? 'Solicitud aprobada.' : 'Solicitud rechazada.');
        this.cargar();
      },
      error: err => this.handleError(err),
    });
  }

  private authHeaders(token: string): HttpHeaders {
    return new HttpHeaders({ Authorization: `Bearer ${token}` });
  }

  private handleError(err: { status?: number }): void {
    if (err?.status === 401) {
      sessionStorage.removeItem('admin_token');
      this._error.set('Sesión administrativa inválida. Vuelve al acceso.');
      return;
    }
    this._error.set('No se pudo completar la operación.');
  }
}