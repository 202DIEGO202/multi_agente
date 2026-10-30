import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

interface DetalleSolicitud {
  id: number;
  tipo_ausencia: string;
  estado: string;
  estado_codigo: string;
  fecha_inicio: string;
  fecha_fin: string;
  hora_inicio: string | null;
  hora_fin: string | null;
  motivo: string | null;
  version: number;
  creado_en: string;
  actualizado_en: string;
}

interface EventoHistorial {
  version: number;
  estado_anterior: string | null;
  estado_nuevo: string;
  evento: string;
  ocurrido_en: string;
}

@Component({
  selector: 'app-notificaciones',
  standalone: true,
  imports: [FormsModule, RouterLink],
  template: `
    <h1>Notificaciones y detalle de solicitud</h1>
    <section class="card">
      <h2>Notificación de cambio de estado</h2>
      <p class="alert">No es posible cargar los avisos: el contrato recibido no ofrece un endpoint público de notificaciones propias. Esto no significa que no existan avisos.</p>
    </section>
    <section class="card">
      <h2>Detalle e historial</h2>
      <form (ngSubmit)="consultar()" novalidate>
        <label class="field">Identificador de solicitud <span aria-hidden="true">*</span><input name="solicitudId" type="number" min="1" step="1" required [ngModel]="identificador()" (ngModelChange)="identificador.set($event)"></label>
        <button type="submit" [disabled]="cargando()">{{ cargando() ? 'Consultando…' : 'Consultar detalle e historial' }}</button>
      </form>
      @if (errorDetalle()) { <p class="error" role="alert">{{ errorDetalle() }}</p> }
      @if (detalle(); as solicitud) {
        <h3>Solicitud {{ solicitud.id }}</h3>
        <p>Tipo de ausencia: {{ solicitud.tipo_ausencia }}</p>
        <p>Estado: <span class="badge">{{ solicitud.estado }}</span></p>
        <p>Fechas: {{ solicitud.fecha_inicio }} - {{ solicitud.fecha_fin }}</p>
        <p>Horas: {{ solicitud.hora_inicio ?? 'No aplica' }} - {{ solicitud.hora_fin ?? 'No aplica' }}</p>
        <p>Observación: {{ solicitud.motivo ?? 'No registrada' }}</p>
        <p>Versión: {{ solicitud.version }}</p>
        <p>Último cambio: {{ solicitud.actualizado_en }}</p>
      }
      @if (errorHistorial()) { <p class="error" role="alert">{{ errorHistorial() }}</p> }
      @if (historial(); as eventos) {
        <h3>Historial</h3>
        @if (eventos.length === 0) {
          <p>No hay eventos disponibles para esta solicitud.</p>
        } @else {
          <table>
            <thead><tr><th>Versión</th><th>Estado anterior</th><th>Nuevo estado</th><th>Evento</th><th>Fecha</th></tr></thead>
            <tbody>
              @for (evento of eventos; track evento.version) {
                <tr><td>{{ evento.version }}</td><td>{{ evento.estado_anterior ?? 'Sin estado anterior' }}</td><td>{{ evento.estado_nuevo }}</td><td>{{ evento.evento }}</td><td>{{ evento.ocurrido_en }}</td></tr>
              }
            </tbody>
          </table>
        }
      }
      @if (!consultado()) { <p>Indique el identificador de una solicitud propia. El servidor verifica la identidad y registra la consulta del historial.</p> }
    </section>
    <a routerLink="/">Volver a solicitudes</a>
  `
})
export class NotificacionesComponent {
  readonly identificador = signal<number | null>(null);
  readonly cargando = signal(false);
  readonly consultado = signal(false);
  readonly detalle = signal<DetalleSolicitud | null>(null);
  readonly historial = signal<EventoHistorial[] | null>(null);
  readonly errorDetalle = signal('');
  readonly errorHistorial = signal('');

  async consultar(): Promise<void> {
    if (this.cargando()) return;
    this.detalle.set(null);
    this.historial.set(null);
    this.errorDetalle.set('');
    this.errorHistorial.set('');
    const id = this.identificador();
    if (id === null || !Number.isSafeInteger(id) || id < 1) {
      this.errorDetalle.set('Indique un identificador de solicitud entero mayor que cero.');
      return;
    }
    this.consultado.set(true);
    this.cargando.set(true);
    try {
      await Promise.all([this.cargarDetalle(id), this.cargarHistorial(id)]);
    } finally {
      this.cargando.set(false);
    }
  }

  private async cargarDetalle(id: number): Promise<void> {
    try {
      const respuesta = await fetch(`/api/portal/solicitudes/${id}`, { credentials: 'same-origin', cache: 'no-store' });
      if (!respuesta.ok) {
        this.errorDetalle.set(await this.mensajeError(respuesta));
        return;
      }
      const datos: DetalleSolicitud = await respuesta.json();
      if (datos.id !== id || typeof datos.tipo_ausencia !== 'string' || typeof datos.estado !== 'string') {
        throw new Error('Respuesta de detalle inválida.');
      }
      this.detalle.set(datos);
    } catch {
      this.errorDetalle.set('No se pudo cargar el detalle de la solicitud. Intente nuevamente.');
    }
  }

  private async cargarHistorial(id: number): Promise<void> {
    try {
      const respuesta = await fetch(`/api/portal/solicitudes/${id}/historial`, { credentials: 'same-origin', cache: 'no-store' });
      if (!respuesta.ok) {
        this.errorHistorial.set(await this.mensajeError(respuesta));
        return;
      }
      const datos: EventoHistorial[] = await respuesta.json();
      if (!Array.isArray(datos) || !datos.every(evento => evento && Number.isInteger(evento.version)
          && typeof evento.estado_nuevo === 'string' && typeof evento.evento === 'string'
          && typeof evento.ocurrido_en === 'string')) {
        throw new Error('Respuesta de historial inválida.');
      }
      this.historial.set(datos);
    } catch {
      this.errorHistorial.set('No se pudo cargar el historial de la solicitud. Intente nuevamente.');
    }
  }

  private async mensajeError(respuesta: Response): Promise<string> {
    if (respuesta.status === 401) return 'Autenticación del empleado requerida. No hay una sesión compatible disponible para esta consulta.';
    if (respuesta.status === 404) return 'Solicitud no disponible para esta identidad';
    if (respuesta.status === 403) return 'Identidad del empleado inactiva o sin permiso';
    try {
      const datos: { detail?: unknown } = await respuesta.json();
      if (typeof datos.detail === 'string') return datos.detail;
    } catch {
      // Una respuesta sin JSON conserva el mensaje de carga.
    }
    return `No se pudo completar la consulta (HTTP ${respuesta.status}). Intente nuevamente.`;
  }
}