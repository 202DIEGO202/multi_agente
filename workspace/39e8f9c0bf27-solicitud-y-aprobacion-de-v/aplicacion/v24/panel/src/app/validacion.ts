import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AdminError, AdminSession } from './admin-session';

interface Pendiente {
  revision_id: number;
  solicitud_id: number;
  version_revision: number;
  version_solicitud: number;
  rol_codigo: string;
  requiere_revision_adicional: boolean;
  solicitante: string;
  tipo_ausencia: string;
  fecha_inicio: string;
  fecha_fin: string;
}
interface Revision {
  id: number;
  version: number;
  estado: string;
  aprobador: string;
  rol_codigo: string;
}
interface Observacion {
  id: number;
  actor: string;
  clase: string;
  contenido: string;
}
interface Detalle {
  id: number;
  version: number;
  estado_codigo: string;
  solicitante: string;
  tipo_ausencia: string;
  fecha_inicio: string;
  fecha_fin: string;
  motivo: string | null;
  requiere_revision_adicional: boolean;
  revisiones: Revision[];
  observaciones: Observacion[];
}
interface Seleccion {
  pendiente: Pendiente;
  detalle: Detalle;
  revision: Revision;
}

@Component({
  selector: 'app-validacion',
  standalone: true,
  imports: [FormsModule],
  template: `
    @if (session.authenticated()) {
      <section class="page">
        <header class="page-header">
          <h1>Validación de Talento Humano</h1>
          <button class="btn" type="button" (click)="session.logout()">Cerrar sesión</button>
        </header>
        @if (error()) { <p class="alert" role="alert">{{ error() }}</p> }
        @if (message()) { <p class="alert" role="status">{{ message() }}</p> }
        <section class="card">
          <h2>Revisor de Talento Humano</h2>
          <p>Nombre: {{ selected()?.revision?.aprobador || 'Seleccione una solicitud para consultar el revisor asignado' }}</p>
          <p>Área: No informada por la API</p>
          <p>Rol: Validador</p>
          <p>Turno: No informado por la API</p>
        </section>
        <section class="card" [attr.aria-busy]="busy()">
          <h2>Solicitudes pendientes</h2>
          <button class="btn" type="button" (click)="cargar()" [disabled]="busy()">Actualizar bandeja</button>
          @if (busy()) { <p role="status">Cargando…</p> }
          @for (item of pendientesTH(); track item.revision_id) {
            <article class="card">
              <p>Solicitante: {{ item.solicitante }} | Tipo: {{ item.tipo_ausencia }} | Fechas: {{ fecha(item.fecha_inicio) }} - {{ fecha(item.fecha_fin) }}</p>
              <button class="btn" type="button" (click)="seleccionar(item)" [disabled]="busy()">Revisar solicitud</button>
            </article>
          } @empty {
            @if (!busy()) { <p>No hay solicitudes pendientes de Talento Humano en esta página.</p> }
          }
          <nav aria-label="Paginación de solicitudes pendientes">
            <button class="btn" type="button" (click)="pagina(-1)" [disabled]="busy() || offset() === 0">Anterior</button>
            <span>Página {{ offset() / limite + 1 }}</span>
            <button class="btn" type="button" (click)="pagina(1)" [disabled]="busy() || filas().length < limite">Siguiente</button>
          </nav>
        </section>
        <section class="card">
          <h2>Solicitud a validar</h2>
          @if (selected(); as item) {
            <p>Solicitante: {{ item.detalle.solicitante }}</p>
            <p>Tipo de ausencia: {{ item.detalle.tipo_ausencia }}</p>
            <p>Fechas: {{ fecha(item.detalle.fecha_inicio) }} - {{ fecha(item.detalle.fecha_fin) }}</p>
            <p>Caso requiere revisión adicional: {{ item.detalle.requiere_revision_adicional ? 'Sí' : 'No' }}</p>
            <p>Observación del empleado: {{ item.detalle.motivo || 'Sin observación' }}</p>
            <h3>Observación previa</h3>
            @for (observacion of item.detalle.observaciones; track observacion.id) {
              <p>{{ observacion.actor }} · {{ observacion.clase }}: {{ observacion.contenido }}</p>
            } @empty {
              <p>Sin observaciones previas registradas.</p>
            }
            <label for="observaciones-th">Observaciones de Talento Humano</label>
            <textarea id="observaciones-th" rows="4" maxlength="5000" [ngModel]="observacion()" (ngModelChange)="observacion.set($event)" [disabled]="busy()"></textarea>
            <p>Las observaciones son opcionales, también al rechazar la solicitud.</p>
            <label for="siguiente-th">Siguiente aprobador (ID)</label>
            <input id="siguiente-th" type="number" min="1" step="1" [ngModel]="siguiente()" (ngModelChange)="siguiente.set($event)" [disabled]="busy()" aria-describedby="ayuda-siguiente-th">
            <p id="ayuda-siguiente-th">Complete únicamente si existe una siguiente etapa todavía no asignada. La API verifica la elegibilidad. No se envía al rechazar.</p>
            <button class="btn btn-primary" type="button" (click)="decidir('VALIDAR_Y_APROBAR')" [disabled]="busy()">Validar y aprobar</button>
            <button class="btn btn-danger" type="button" (click)="decidir('RECHAZAR')" [disabled]="busy()">Rechazar solicitud</button>
          } @else {
            <p>Seleccione una solicitud pendiente para validar.</p>
          }
        </section>
      </section>
    }
  `
})
export class Validacion {
  readonly session = inject(AdminSession);
  readonly filas = signal<Pendiente[]>([]);
  readonly pendientesTH = computed(() => this.filas().filter(item => item.rol_codigo === 'talento_humano'));
  readonly selected = signal<Seleccion | null>(null);
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
    if (this.busy() || !this.session.hasToken() || item.rol_codigo !== 'talento_humano') return;
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    this.selected.set(null);
    this.observacion.set('');
    this.siguiente.set(null);
    try {
      const detalle = await this.session.request<Detalle>(`/api/admin/solicitudes/${item.solicitud_id}`);
      if (!this.alive || !this.session.authenticated()) return;
      const revision = detalle.revisiones.find(row => row.id === item.revision_id);
      if (!revision || revision.rol_codigo !== 'talento_humano' || detalle.estado_codigo !== 'EN_REVISION' || !['PENDIENTE', 'EN_REVISION'].includes(revision.estado)) {
        this.error.set('La solicitud ya no está pendiente de validación. Actualice la bandeja.');
        return;
      }
      this.selected.set({ pendiente: item, detalle, revision });
    } catch (error) { this.report(error); }
    finally { this.busy.set(false); }
  }

  async decidir(decision: 'VALIDAR_Y_APROBAR' | 'RECHAZAR'): Promise<void> {
    const item = this.selected();
    if (!item || this.busy() || !this.session.hasToken()) return;
    const observacion = this.observacion().trim();
    const siguiente = this.siguiente();
    if (decision === 'VALIDAR_Y_APROBAR' && siguiente !== null && (!Number.isInteger(siguiente) || siguiente < 1)) {
      this.error.set('El ID del siguiente aprobador debe ser un entero positivo.');
      return;
    }
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    let recargar = false;
    try {
      await this.session.request<unknown>(`/api/admin/revisiones/${item.revision.id}/decision`, 'POST', {
        decision,
        version_solicitud_esperada: item.detalle.version,
        version_revision_esperada: item.revision.version,
        ...(observacion ? { observacion } : {}),
        ...(decision === 'VALIDAR_Y_APROBAR' && siguiente !== null ? { siguiente_aprobador_id: siguiente } : {})
      });
      if (!this.alive || !this.session.authenticated()) return;
      this.message.set(decision === 'VALIDAR_Y_APROBAR'
        ? 'Solicitud validada y aprobada. La decisión y las observaciones quedaron registradas.'
        : 'Solicitud rechazada. La decisión y las observaciones quedaron registradas.');
      this.selected.set(null);
      this.observacion.set('');
      this.siguiente.set(null);
      recargar = true;
    } catch (error) {
      if (error instanceof AdminError && error.status === 409 && this.alive && this.session.authenticated()) {
        this.selected.set(null);
        this.message.set('La solicitud cambió o ya fue decidida. Actualice la bandeja y vuelva a seleccionar la solicitud antes de decidir.');
      }
      this.report(error);
    } finally { this.busy.set(false); }
    if (recargar) await this.cargar();
  }
}