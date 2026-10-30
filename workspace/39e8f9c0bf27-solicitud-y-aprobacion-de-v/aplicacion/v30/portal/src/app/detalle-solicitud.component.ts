import { Component, DestroyRef, inject, signal } from '@angular/core';
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
  private readonly destroyRef = inject(DestroyRef);
  private controlador: AbortController | null = null;
  readonly id = signal('');
  readonly cargando = signal(false);
  readonly solicitud = signal<Detalle | null>(null);
  readonly historial = signal<Evento[]>([]);
  readonly notificaciones = signal<Notificacion[]>([]);
  readonly errorDetalle = signal('');
  readonly errorHistorial = signal('');
  readonly errorNotificaciones = signal('');

  constructor() {
    this.destroyRef.onDestroy(() => this.controlador?.abort());
    this.route.paramMap.pipe(takeUntilDestroyed()).subscribe(params => {
      this.id.set(params.get('id') || '');
      void this.cargar(this.id());
    });
  }

  async cargar(id: string): Promise<void> {
    this.controlador?.abort();
    const controlador = new AbortController();
    this.controlador = controlador;
    const sesion = controlador.signal;
    this.cargando.set(false);
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
    this.cargando.set(true);
    const ruta = `/api/empleado/solicitudes/${id}`;
    try {
      // Cada consulta conserva la autorización de la sesión del empleado.
      await Promise.all([
        (async () => {
          try {
            const detalle = await this.consultar<Detalle>(ruta, sesion);
            if (!sesion.aborted) this.solicitud.set(detalle);
          } catch (error) {
            if (!sesion.aborted) this.errorDetalle.set(this.textoError(error));
          }
        })(),
        (async () => {
          try {
            const eventos = await this.consultarPaginas<Evento>(`${ruta}/historial`, sesion);
            if (!sesion.aborted) this.historial.set(eventos);
          } catch (error) {
            if (!sesion.aborted) this.errorHistorial.set(this.textoError(error));
          }
        })(),
        (async () => {
          try {
            const avisos = await this.consultarPaginas<Notificacion>('/api/empleado/notificaciones', sesion);
            if (!sesion.aborted) this.notificaciones.set(avisos.filter(aviso => aviso.solicitud_id === Number(id)));
          } catch (error) {
            if (!sesion.aborted) this.errorNotificaciones.set(this.textoError(error));
          }
        })()
      ]);
    } finally {
      if (!sesion.aborted) this.cargando.set(false);
    }
  }

  private async consultarPaginas<T>(ruta: string, sesion: AbortSignal): Promise<T[]> {
    const filas: T[] = [];
    for (let offset = 0; ; offset += 100) {
      const pagina = await this.consultar<T[]>(`${ruta}?limit=100&offset=${offset}`, sesion);
      filas.push(...pagina);
      if (pagina.length < 100) return filas;
    }
  }

  private async consultar<T>(ruta: string, sesion: AbortSignal): Promise<T> {
    const respuesta = await fetch(ruta, { credentials: 'same-origin', cache: 'no-store', signal: sesion });
    const datos: unknown = await respuesta.json().catch(() => null);
    if (!respuesta.ok) {
      const detalle = datos && typeof datos === 'object' && 'detail' in datos ? datos.detail : null;
      if (typeof detalle === 'string') throw new Error(detalle);
      if (Array.isArray(detalle)) {
        const mensajes = detalle.map(item => item && typeof item.msg === 'string' ? item.msg : '').filter(Boolean);
        if (mensajes.length) throw new Error(mensajes.join(' '));
      }
      throw new Error(`No se pudo completar la consulta (${respuesta.status}).`);
    }
    if (datos === null) throw new Error('La API devolvió una respuesta no válida.');
    return datos as T;
  }

  private textoError(error: unknown): string {
    return error instanceof Error ? error.message : 'No se pudo contactar con la API. Inténtelo de nuevo.';
  }
}