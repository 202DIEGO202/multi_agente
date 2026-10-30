import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AdminError, AdminSession } from './admin-session';

interface Pendiente {
  revision_id: number;
  solicitud_id: number;
  version_revision: number;
  version_solicitud: number;
  rol_codigo: string;
  estado_revision: string;
  requiere_validacion: boolean;
  requiere_revision_adicional: boolean;
  solicitante: string;
  area: string;
  tipo_ausencia: string;
  fecha_inicio: string;
  fecha_fin: string;
  hora_inicio: string | null;
  hora_fin: string | null;
  observacion_empleado: string | null;
}
interface Revision {
  id: number;
  version: number;
  estado: string;
  orden: number;
  aprobador_id: number;
}
interface Detalle {
  id: number;
  version: number;
  estado_codigo: string;
  solicitante: string;
  area: string;
  tipo_ausencia: string;
  fecha_inicio: string;
  fecha_fin: string;
  hora_inicio: string | null;
  hora_fin: string | null;
  motivo: string | null;
  revisiones: Revision[];
}

@Component({
  selector: 'app-bandeja-revision',
  standalone: true,
  imports: [FormsModule],
  template: `
    @if (session.authenticated()) {
      <section class="page">
        <header class="page-header">
          <h1>Bandeja de revisión - Jefe inmediato</h1>
          <button class="btn" type="button" (click)="session.logout()">Cerrar sesión</button>
        </header>
        @if (error()) { <p class="alert" role="alert">{{ error() }}</p> }
        @if (message()) { <p class="alert" role="status">{{ message() }}</p> }
        <section class="card" [attr.aria-busy]="busy()">
          <h2>Solicitudes pendientes</h2>
          <button class="btn" type="button" (click)="cargar()" [disabled]="busy()">Actualizar bandeja</button>
          @if (busy()) { <p role="status">Cargando…</p> }
          @for (item of pendientesJefe(); track item.revision_id) {
            <article class="card">
              <p>Solicitante: {{ item.solicitante }} | Tipo: {{ item.tipo_ausencia }} |
                @if (item.fecha_inicio === item.fecha_fin) {
                  Fecha: {{ fecha(item.fecha_inicio) }}
                } @else {
                  Fechas: {{ fecha(item.fecha_inicio) }} - {{ fecha(item.fecha_fin) }}
                }
              </p>
              <button class="btn" type="button" (click)="seleccionar(item)" [disabled]="busy()">Revisar solicitud</button>
            </article>
          } @empty {
            @if (!busy()) { <p>No hay solicitudes pendientes de jefe inmediato en esta página.</p> }
          }
          <nav aria-label="Paginación de solicitudes pendientes">
            <button class="btn" type="button" (click)="pagina(-1)" [disabled]="busy() || offset() === 0">Anterior</button>
            <span>Página {{ offset() / limite + 1 }}</span>
            <button class="btn" type="button" (click)="pagina(1)" [disabled]="busy() || filas().length < limite">Siguiente</button>
          </nav>
        </section>
        @if (selected(); as item) {
          <section class="card">
            <h2>Solicitud en revisión</h2>
            <p>Solicitante: {{ item.solicitante }}</p>
            <p>Área: {{ item.area }}</p>
            <p>Tipo de ausencia: {{ item.tipo_ausencia }}</p>
            <p>Fechas: {{ fecha(item.fecha_inicio) }} - {{ fecha(item.fecha_fin) }}</p>
            @if (item.hora_inicio || item.hora_fin) { <p>Horas: {{ item.hora_inicio || '—' }} - {{ item.hora_fin || '—' }}</p> }
            <p>Observación del empleado: {{ item.observacion_empleado || 'Sin observación' }}</p>
            <label for="observacion-jefe">Observaciones de revisión del jefe</label>
            <textarea id="observacion-jefe" rows="4" maxlength="5000" [ngModel]="observacion()" (ngModelChange)="observacion.set($event)" [disabled]="busy()"></textarea>
            <p>Las observaciones son opcionales, también al rechazar la solicitud.</p>
            <label for="siguiente-aprobador">Siguiente aprobador (ID)</label>
            <input id="siguiente-aprobador" type="number" min="1" step="1" [ngModel]="siguiente()" (ngModelChange)="siguiente.set($event)" [disabled]="busy()" aria-describedby="ayuda-siguiente">
            <p id="ayuda-siguiente">Complete únicamente si el flujo tiene una siguiente etapa todavía no asignada. La API comprueba el rol y la elegibilidad del aprobador. No se envía este campo al rechazar.</p>
            <button class="btn btn-primary" type="button" (click)="decidir('APROBAR')" [disabled]="busy() || item.requiere_validacion">Aprobar solicitud</button>
            <button class="btn btn-danger" type="button" (click)="decidir('RECHAZAR')" [disabled]="busy()">Rechazar solicitud</button>
            @if (item.requiere_validacion) { <p>Esta etapa requiere validación y no admite aprobación simple del jefe inmediato.</p> }
          </section>
        }
      </section>
    }
  `
})
export class BandejaRevision {
  readonly session = inject(AdminSession);
  readonly filas = signal<Pendiente[]>([]);
  readonly pendientesJefe = computed(() => this.filas().filter(item => item.rol_codigo === 'jefe_inmediato'));
  readonly selected = signal<Pendiente | null>(null);
  readonly observacion = signal('');
  readonly siguiente = signal<number | null>(null);
  readonly offset = signal(0);
  readonly limite = 50;
  readonly busy = signal(false);
  readonly error = signal('');
  readonly message = signal('');
  private alive = true;

  constructor() {
    inject(DestroyRef).onDestroy(() => {
      this.alive = false;
      this.filas.set([]);
      this.selected.set(null);
    });
    void this.cargar();
  }

  fecha(value: string): string {
    const parts = value.slice(0, 10).split('-');
    return parts.length === 3 ? `${parts[2]}/${parts[1]}/${parts[0]}` : value;
  }

  private report(error: unknown): void {
    if (!this.alive || !this.session.authenticated()) return;
    this.error.set(error instanceof Error ? error.message : 'La operación no se pudo completar.');
  }

  async cargar(): Promise<void> {
    if (this.busy() || !this.session.hasToken()) return;
    this.busy.set(true);
    this.error.set('');
    this.selected.set(null);
    this.filas.set([]);
    try {
      const rows = await this.session.request<Pendiente[]>(`/api/admin/revisiones/pendientes?limite=${this.limite}&offset=${this.offset()}`);
      if (this.alive && this.session.authenticated()) this.filas.set(rows);
    } catch (error) { this.report(error); }
    finally { this.busy.set(false); }
  }

  pagina(direction: number): void {
    if (this.busy()) return;
    this.offset.update(value => Math.max(0, value + direction * this.limite));
    this.message.set('');
    void this.cargar();
  }

  async seleccionar(item: Pendiente): Promise<void> {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    this.selected.set(null);
    this.observacion.set('');
    this.siguiente.set(null);
    try {
      const detail = await this.session.request<Detalle>(`/api/admin/solicitudes/${item.solicitud_id}`);
      if (!this.alive || !this.session.authenticated()) return;
      const revision = detail.revisiones.find(row => row.id === item.revision_id);
      if (!revision || detail.estado_codigo !== 'EN_REVISION' || !['PENDIENTE', 'EN_REVISION'].includes(revision.estado)) {
        this.error.set('La solicitud ya no está pendiente. Actualice la bandeja.');
        return;
      }
      this.selected.set({
        ...item,
        version_solicitud: detail.version,
        version_revision: revision.version,
        solicitante: detail.solicitante,
        area: detail.area,
        tipo_ausencia: detail.tipo_ausencia,
        fecha_inicio: detail.fecha_inicio,
        fecha_fin: detail.fecha_fin,
        hora_inicio: detail.hora_inicio,
        hora_fin: detail.hora_fin,
        observacion_empleado: detail.motivo
      });
    } catch (error) { this.report(error); }
    finally { this.busy.set(false); }
  }

  async decidir(decision: 'APROBAR' | 'RECHAZAR'): Promise<void> {
    const item = this.selected();
    if (!item || this.busy() || !this.session.hasToken()) return;
    const observacion = this.observacion().trim();
    if (decision === 'APROBAR' && item.requiere_validacion) { this.error.set('Esta etapa requiere validación.'); return; }
    const siguiente = this.siguiente();
    if (decision === 'APROBAR' && siguiente !== null && (!Number.isInteger(siguiente) || siguiente < 1)) {
      this.error.set('El ID del siguiente aprobador debe ser un entero positivo.');
      return;
    }
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    let recargar = false;
    try {
      await this.session.request<unknown>(`/api/admin/revisiones/${item.revision_id}/decision`, 'POST', {
        decision,
        version_solicitud_esperada: item.version_solicitud,
        version_revision_esperada: item.version_revision,
        ...(observacion ? { observacion } : {}),
        ...(decision === 'APROBAR' && siguiente !== null ? { siguiente_aprobador_id: siguiente } : {})
      });
      if (!this.alive || !this.session.authenticated()) return;
      this.message.set(decision === 'APROBAR' ? 'Solicitud aprobada. La decisión y las observaciones quedaron registradas.' : 'Solicitud rechazada. La decisión y las observaciones quedaron registradas.');
      this.selected.set(null);
      this.observacion.set('');
      this.siguiente.set(null);
      recargar = true;
    } catch (error) {
      if (error instanceof AdminError && error.status === 409) {
        this.selected.set(null);
        this.message.set('La solicitud cambió o ya fue decidida. Actualice la bandeja y vuelva a seleccionar la solicitud antes de decidir.');
      }
      this.report(error);
    } finally { this.busy.set(false); }
    if (recargar) await this.cargar();
  }
}