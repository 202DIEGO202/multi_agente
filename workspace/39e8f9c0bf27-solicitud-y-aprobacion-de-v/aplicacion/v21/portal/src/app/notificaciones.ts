import { Component, DestroyRef, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { PortalApi } from './portal-api';

interface Detalle { id: number; tipo_ausencia: string; estado: string; estado_codigo: string; fecha_inicio: string; fecha_fin: string; hora_inicio: string | null; hora_fin: string | null; motivo: string | null; version: number; }
interface Evento { version: number; estado_anterior: string | null; estado_nuevo: string; evento: string; ocurrido_en: string; }
interface Aviso { id: number; solicitud_id: number; asunto: string; mensaje: string; creada_en: string; leida_en: string | null; tipo_ausencia: string; fecha_inicio: string; fecha_fin: string; estado_anterior: string | null; estado_anterior_nombre: string | null; estado_nuevo: string; estado_nuevo_nombre: string; fecha_cambio: string; }

@Component({
  selector: 'app-notificaciones',
  standalone: true,
  imports: [RouterLink],
  template: `
    <section>
      <h1>Notificaciones y detalle de solicitud</h1>
      <section class="card" [attr.aria-busy]="cargandoAvisos()">
        <h2>Notificación de cambio de estado</h2>
        <button class="secondary" type="button" (click)="cargarNotificaciones()" [disabled]="cargandoAvisos()">Actualizar notificaciones</button>
        @if (cargandoAvisos()) { <p role="status">Cargando notificaciones…</p> }
        @if (errorAvisos()) { <p class="error" role="alert">{{ errorAvisos() }}</p> }
        @for (aviso of avisos(); track aviso.id) {
          <article class="card">
            <h3>{{ aviso.asunto }}</h3>
            <p>{{ aviso.mensaje }}</p>
            <p>Solicitud: {{ aviso.solicitud_id }} | Tipo de ausencia: {{ aviso.tipo_ausencia }}</p>
            <p>Fechas: {{ aviso.fecha_inicio }} - {{ aviso.fecha_fin }}</p>
            <p>Estado anterior: {{ aviso.estado_anterior_nombre || aviso.estado_anterior || 'Sin estado anterior' }}</p>
            <p>Nuevo estado: {{ aviso.estado_nuevo_nombre || aviso.estado_nuevo }}</p>
            <p>Fecha del aviso: {{ aviso.creada_en }}</p>
            <a routerLink="/notificaciones" [queryParams]="{ solicitud_id: aviso.solicitud_id }">Consultar detalle e historial</a>
          </article>
        } @empty {
          @if (!cargandoAvisos() && !errorAvisos()) { <p>No tiene notificaciones de cambio de estado.</p> }
        }
        <nav aria-label="Paginación de notificaciones">
          <button class="secondary" type="button" (click)="pagina(-1)" [disabled]="cargandoAvisos() || offset() === 0">Anterior</button>
          <span>Página {{ offset() / limite + 1 }}</span>
          <button class="secondary" type="button" (click)="pagina(1)" [disabled]="cargandoAvisos() || avisos().length < limite">Siguiente</button>
        </nav>
      </section>
      <section class="card" [attr.aria-busy]="cargandoDetalle()">
        <h2>Detalle e historial</h2>
        @if (cargandoDetalle()) { <p role="status">Cargando detalle…</p> }
        @if (errorDetalle()) { <p class="error" role="alert">{{ errorDetalle() }}</p> }
        @if (detalle(); as solicitud) {
          <p>Solicitud: {{ solicitud.id }}</p>
          <p>Tipo de ausencia: {{ solicitud.tipo_ausencia }}</p>
          <p>Estado: {{ solicitud.estado || solicitud.estado_codigo }}</p>
          <p>Fechas: {{ solicitud.fecha_inicio }} - {{ solicitud.fecha_fin }}</p>
          <p>Horas: {{ solicitud.hora_inicio ? solicitud.hora_inicio + ' - ' + solicitud.hora_fin : 'No aplica' }}</p>
          <p>Observación: {{ solicitud.motivo || 'Sin observación' }}</p>
        } @else {
          @if (!solicitudId() && !errorDetalle()) { <p>Seleccione una solicitud desde su historial o una notificación.</p> }
        }
        @if (cargandoHistorial()) { <p role="status">Cargando historial…</p> }
        @if (errorHistorial()) { <p class="error" role="alert">{{ errorHistorial() }}</p> }
        @for (evento of historial(); track evento.version) {
          <article>
            <p>{{ evento.ocurrido_en }} · {{ evento.evento }}</p>
            <p>Estado anterior: {{ evento.estado_anterior || 'Sin estado anterior' }} | Nuevo estado: {{ evento.estado_nuevo }}</p>
          </article>
        } @empty {
          @if (solicitudId() && !cargandoHistorial() && !errorHistorial()) { <p>No hay eventos de historial.</p> }
        }
      </section>
      <a routerLink="/">Volver a solicitudes</a>
    </section>
  `
})
export class NotificacionesComponent {
  private readonly api = inject(PortalApi);
  private readonly route = inject(ActivatedRoute);
  readonly solicitudId = signal<number | null>(null);
  readonly detalle = signal<Detalle | null>(null);
  readonly historial = signal<Evento[]>([]);
  readonly avisos = signal<Aviso[]>([]);
  readonly cargandoDetalle = signal(false);
  readonly cargandoHistorial = signal(false);
  readonly cargandoAvisos = signal(false);
  readonly errorDetalle = signal('');
  readonly errorHistorial = signal('');
  readonly errorAvisos = signal('');
  readonly offset = signal(0);
  readonly limite = 50;
  private alive = true;
  private selectionGeneration = 0;

  constructor() {
    const subscription = this.route.queryParamMap.subscribe(params => {
      const raw = params.get('solicitud_id');
      const id = raw === null ? null : Number(raw);
      this.selectionGeneration++;
      this.detalle.set(null); this.historial.set([]);
      this.errorDetalle.set(''); this.errorHistorial.set('');
      this.cargandoDetalle.set(false); this.cargandoHistorial.set(false);
      if (id !== null && (!Number.isSafeInteger(id) || id < 1)) {
        this.solicitudId.set(null);
        this.errorDetalle.set('El enlace de la solicitud no es válido.');
        return;
      }
      this.solicitudId.set(id);
      if (id !== null) { void this.cargarDetalle(); void this.cargarHistorial(); }
    });
    inject(DestroyRef).onDestroy(() => { this.alive = false; subscription.unsubscribe(); });
    void this.cargarNotificaciones();
  }

  async cargarDetalle(): Promise<void> {
    const id = this.solicitudId();
    if (id === null) return;
    const generation = this.selectionGeneration;
    this.cargandoDetalle.set(true);
    this.errorDetalle.set('');
    try {
      const detalle = await this.api.consultar<Detalle>(`/api/portal/solicitudes/${id}`);
      if (this.alive && generation === this.selectionGeneration) this.detalle.set(detalle);
    } catch (error) {
      if (this.alive && generation === this.selectionGeneration) this.errorDetalle.set(this.api.mensaje(error));
    } finally { if (generation === this.selectionGeneration) this.cargandoDetalle.set(false); }
  }

  async cargarHistorial(): Promise<void> {
    const id = this.solicitudId();
    if (id === null) return;
    const generation = this.selectionGeneration;
    this.cargandoHistorial.set(true);
    this.errorHistorial.set('');
    try {
      const historial = await this.api.consultar<Evento[]>(`/api/portal/solicitudes/${id}/historial`);
      if (this.alive && generation === this.selectionGeneration) this.historial.set(historial);
    } catch (error) {
      if (this.alive && generation === this.selectionGeneration) this.errorHistorial.set(this.api.mensaje(error));
    } finally { if (generation === this.selectionGeneration) this.cargandoHistorial.set(false); }
  }

  async cargarNotificaciones(): Promise<void> {
    if (this.cargandoAvisos()) return;
    this.cargandoAvisos.set(true);
    this.errorAvisos.set('');
    this.avisos.set([]);
    try {
      const avisos = await this.api.consultar<Aviso[]>(`/api/portal/notificaciones?limite=${this.limite}&offset=${this.offset()}`);
      if (this.alive) this.avisos.set(avisos);
    } catch (error) { if (this.alive) this.errorAvisos.set(this.api.mensaje(error)); }
    finally { this.cargandoAvisos.set(false); }
  }

  pagina(direction: number): void {
    if (this.cargandoAvisos()) return;
    this.offset.update(value => Math.max(0, value + direction * this.limite));
    void this.cargarNotificaciones();
  }
}