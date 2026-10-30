import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

interface Detalle {
  id: number;
  tipo_ausencia: string;
  fecha_inicio: string;
  fecha_fin: string;
  hora_inicio: string | null;
  hora_fin: string | null;
  motivo: string | null;
  estado_codigo: string;
  version: number;
}
interface Evento {
  id: number;
  operacion: string;
  estado_anterior: string | null;
  estado_nuevo: string | null;
  version: number;
  creado_en: string;
}
interface Notificacion {
  id: number;
  solicitud_id: number;
  estado_notificado: string | null;
  creado_en: string;
  enviada_en: string | null;
}

@Component({
  selector: 'app-detalle-solicitud',
  standalone: true,
  imports: [RouterLink],
  template: `
    <h1>Notificaciones y detalle de solicitud</h1>
    @if (cargando()) { <p role="status">Cargando detalle…</p> }
    @if (errorDetalle()) { <p class="error" role="alert">{{ errorDetalle() }}</p> }
    <section class="card" aria-labelledby="cambio">
      <h2 id="cambio">Notificación de cambio de estado</h2>
      @if (errorNotificaciones()) { <p class="error" role="alert">{{ errorNotificaciones() }}</p> }
      @for (aviso of notificaciones(); track aviso.id) {
        <article>
          <p>Solicitud: #{{ aviso.solicitud_id }}</p>
          <p>Nuevo estado: {{ aviso.estado_notificado || 'No disponible' }}</p>
          <p>Fecha del aviso: {{ aviso.enviada_en || aviso.creado_en }}</p>
        </article>
      } @empty {
        @if (!cargando() && !errorNotificaciones()) { <p>No hay avisos de cambio de estado disponibles para esta solicitud.</p> }
      }
    </section>
    <section class="card" aria-labelledby="pendientes">
      <h2 id="pendientes">Notificación de pendientes de revisión</h2>
      <p>Los avisos de revisión se destinan al aprobador correspondiente. Este portal muestra únicamente los avisos propios del empleado.</p>
    </section>
    <section class="card" aria-labelledby="detalle">
      <h2 id="detalle">Detalle e historial</h2>
      @if (solicitud(); as detalle) {
        <p>Solicitud: #{{ detalle.id }}</p>
        <p>Tipo de ausencia: {{ detalle.tipo_ausencia }}</p>
        <p>Fechas: {{ detalle.fecha_inicio }} - {{ detalle.fecha_fin }}</p>
        <p>Horas: {{ detalle.hora_inicio || 'No aplica' }} @if (detalle.hora_fin) { - {{ detalle.hora_fin }} }</p>
        <p>Observación: {{ detalle.motivo || 'Sin observación' }}</p>
        <p>Estado: <span class="badge">{{ detalle.estado_codigo }}</span></p>
        <p>Versión: {{ detalle.version }}</p>
      }
      @if (errorHistorial()) { <p class="error" role="alert">{{ errorHistorial() }}</p> }
      @if (historial().length) {
        <table>
          <thead><tr><th>Operación</th><th>Estado anterior</th><th>Nuevo estado</th><th>Versión</th><th>Fecha</th></tr></thead>
          <tbody>
            @for (evento of historial(); track evento.id) {
              <tr><td>{{ evento.operacion }}</td><td>{{ evento.estado_anterior || '—' }}</td><td>{{ evento.estado_nuevo || '—' }}</td><td>{{ evento.version }}</td><td>{{ evento.creado_en }}</td></tr>
            }
          </tbody>
        </table>
      } @else if (!cargando() && solicitud() && !errorHistorial()) { <p>No hay eventos de historial disponibles.</p> }
    </section>
    <div class="actions">
      <button type="button" class="secondary" routerLink="/">Volver a solicitudes</button>
      <button type="button" class="secondary" (click)="cargar(id())" [disabled]="cargando() || !id()">Actualizar</button>
    </div>
  `
})
export class DetalleSolicitudComponent {
  private readonly route = inject(ActivatedRoute);
  readonly id = signal('');
  readonly cargando = signal(false);
  readonly solicitud = signal<Detalle | null>(null);
  readonly historial = signal<Evento[]>([]);
  readonly notificaciones = signal<Notificacion[]>([]);
  readonly errorDetalle = signal('');
  readonly errorHistorial = signal('');
  readonly errorNotificaciones = signal('');

  constructor() {
    this.route.paramMap.pipe(takeUntilDestroyed()).subscribe(params => {
      this.id.set(params.get('id') || '');
      void this.cargar(this.id());
    });
  }

  async cargar(id: string): Promise<void> {
    this.solicitud.set(null);
    this.historial.set([]);
    this.notificaciones.set([]);
    this.errorDetalle.set('');
    this.errorHistorial.set('');
    this.errorNotificaciones.set('');
    if (!/^[1-9]\d*$/.test(id) || !Number.isSafeInteger(Number(id))) {
      this.errorDetalle.set('El identificador de solicitud debe ser un entero positivo. No se ha realizado ninguna consulta.');
      return;
    }
    this.errorDetalle.set('No se ha consultado el detalle: no hay un endpoint público autorizado para esta operación.');
    this.errorHistorial.set('No se ha consultado el historial: no hay un endpoint público autorizado para esta operación.');
    this.errorNotificaciones.set('No se han consultado los avisos: no hay un endpoint público autorizado para esta operación.');
  }
}