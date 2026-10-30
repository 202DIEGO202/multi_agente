import { Component, DestroyRef, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { PortalAuth } from './auth.service';

interface Detalle { id: number; tipo_ausencia: string; estado: string; estado_codigo: string; fecha_inicio: string; fecha_fin: string; hora_inicio: string | null; hora_fin: string | null; motivo: string | null; version: number; }
interface Evento { version: number; estado_anterior: string | null; estado_nuevo: string; evento: string; ocurrido_en: string; }
interface Aviso { id: number; solicitud_id: number; asunto: string; mensaje: string; creada_en: string; leida_en: string | null; tipo_ausencia: string; fecha_inicio: string; fecha_fin: string; estado_anterior: string | null; estado_anterior_nombre: string | null; estado_nuevo: string; estado_nuevo_nombre: string; fecha_cambio: string; }

@Component({
  selector: 'app-notificaciones',
  standalone: true,
  imports: [RouterLink],
  template: `
    <section class="page">
      <h1>Notificaciones y seguimiento de solicitudes</h1>
      @if (!auth.authenticated()) {
        <p class="alert" role="alert">{{ auth.message() || 'Acceda con su credencial de empleado para consultar sus solicitudes.' }}</p>
        <a class="btn" routerLink="/">Ir al acceso</a>
      } @else {
        <section class="card" [attr.aria-busy]="cargandoAvisos()">
          <h2>Notificación de cambio de estado</h2>
          <button class="btn" type="button" (click)="cargarNotificaciones()" [disabled]="cargandoAvisos()">Actualizar notificaciones</button>
          @if (cargandoAvisos()) { <p role="status">Cargando notificaciones…</p> }
          @if (errorAvisos()) { <p class="alert" role="alert">{{ errorAvisos() }}</p> }
          @for (aviso of avisos(); track aviso.id) {
            <article class="card">
              <h3>{{ aviso.asunto }}</h3>
              <p>{{ aviso.mensaje }}</p>
              <p>Solicitud: {{ aviso.solicitud_id }} | Tipo de ausencia: {{ aviso.tipo_ausencia }}</p>
              <p>Fechas: {{ aviso.fecha_inicio }} - {{ aviso.fecha_fin }}</p>
              <p>Estado anterior: {{ aviso.estado_anterior_nombre || aviso.estado_anterior || 'Sin estado anterior' }}</p>
              <p>Nuevo estado: {{ aviso.estado_nuevo_nombre || aviso.estado_nuevo }}</p>
              <p>Fecha del cambio: {{ aviso.fecha_cambio }}</p>
              <a class="btn" routerLink="/notificaciones" [queryParams]="{ solicitud_id: aviso.solicitud_id }">Ver detalle e historial</a>
            </article>
          } @empty {
            @if (!cargandoAvisos() && !errorAvisos()) { <p>No tiene notificaciones de cambio de estado.</p> }
          }
          <nav aria-label="Paginación de notificaciones">
            <button class="btn" type="button" (click)="pagina(-1)" [disabled]="cargandoAvisos() || offset() === 0">Anterior</button>
            <span>Página {{ offset() / limite + 1 }}</span>
            <button class="btn" type="button" (click)="pagina(1)" [disabled]="cargandoAvisos() || avisos().length < limite">Siguiente</button>
          </nav>
        </section>
        <section class="card" [attr.aria-busy]="cargandoDetalle()">
          <h2>Detalle de la solicitud</h2>
          @if (cargandoDetalle()) { <p role="status">Cargando detalle…</p> }
          @if (errorDetalle()) { <p class="alert" role="alert">{{ errorDetalle() }}</p> }
          @if (detalle(); as solicitud) {
            <p>Solicitud: {{ solicitud.id }}</p>
            <p>Tipo de ausencia: {{ solicitud.tipo_ausencia }}</p>
            <p>Estado: {{ solicitud.estado || solicitud.estado_codigo }}</p>
            <p>Fechas: {{ solicitud.fecha_inicio }} - {{ solicitud.fecha_fin }}</p>
            @if (solicitud.hora_inicio) { <p>Horas: {{ solicitud.hora_inicio }} - {{ solicitud.hora_fin }}</p> }
            <p>Motivo u observación: {{ solicitud.motivo || 'Sin observación' }}</p>
          } @else {
            @if (!solicitudId()) { <p>Seleccione una solicitud desde su historial o una notificación.</p> }
          }
        </section>
        <section class="card" [attr.aria-busy]="cargandoHistorial()">
          <h2>Historial de la solicitud</h2>
          @if (cargandoHistorial()) { <p role="status">Cargando historial…</p> }
          @if (errorHistorial()) { <p class="alert" role="alert">{{ errorHistorial() }}</p> }
          @for (evento of historial(); track evento.version) {
            <article>
              <p>{{ evento.ocurrido_en }} · {{ evento.evento }}</p>
              <p>Estado anterior: {{ evento.estado_anterior || 'Sin estado anterior' }} | Nuevo estado: {{ evento.estado_nuevo }}</p>
            </article>
          } @empty {
            @if (solicitudId() && !cargandoHistorial() && !errorHistorial()) { <p>No hay eventos de historial.</p> }
          }
        </section>
        <a class="btn" routerLink="/">Volver a mis solicitudes</a>
      }
    </section>
  `
})
export class Notificaciones {
  readonly auth = inject(PortalAuth);
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
      if (id !== null && this.auth.hasToken()) { void this.cargarDetalle(); void this.cargarHistorial(); }
    });
    inject(DestroyRef).onDestroy(() => { this.alive = false; subscription.unsubscribe(); });
    if (this.auth.hasToken()) void this.cargarNotificaciones();
  }

  private mensaje(error: unknown): string { return error instanceof Error ? error.message : 'No se pudo completar la consulta.'; }

  async cargarDetalle(): Promise<void> {
    const id = this.solicitudId();
    if (id === null || !this.auth.hasToken()) return;
    const generation = this.selectionGeneration;
    this.cargandoDetalle.set(true);
    this.errorDetalle.set('');
    try {
      const detalle = await this.auth.request<Detalle>(`/api/portal/solicitudes/${id}`);
      if (this.alive && generation === this.selectionGeneration && this.auth.authenticated()) this.detalle.set(detalle);
    } catch (error) {
      if (this.alive && generation === this.selectionGeneration && this.auth.authenticated()) this.errorDetalle.set(this.mensaje(error));
    } finally { if (generation === this.selectionGeneration) this.cargandoDetalle.set(false); }
  }

  async cargarHistorial(): Promise<void> {
    const id = this.solicitudId();
    if (id === null || !this.auth.hasToken()) return;
    const generation = this.selectionGeneration;
    this.cargandoHistorial.set(true);
    this.errorHistorial.set('');
    try {
      const historial = await this.auth.request<Evento[]>(`/api/portal/solicitudes/${id}/historial`);
      if (this.alive && generation === this.selectionGeneration && this.auth.authenticated()) this.historial.set(historial);
    } catch (error) {
      if (this.alive && generation === this.selectionGeneration && this.auth.authenticated()) this.errorHistorial.set(this.mensaje(error));
    } finally { if (generation === this.selectionGeneration) this.cargandoHistorial.set(false); }
  }

  async cargarNotificaciones(): Promise<void> {
    if (this.cargandoAvisos() || !this.auth.hasToken()) return;
    this.cargandoAvisos.set(true);
    this.errorAvisos.set('');
    this.avisos.set([]);
    try {
      const avisos = await this.auth.request<Aviso[]>(`/api/portal/notificaciones?limite=${this.limite}&offset=${this.offset()}`);
      if (this.alive && this.auth.authenticated()) this.avisos.set(avisos);
    } catch (error) { if (this.alive && this.auth.authenticated()) this.errorAvisos.set(this.mensaje(error)); }
    finally { this.cargandoAvisos.set(false); }
  }

  pagina(direction: number): void {
    if (this.cargandoAvisos()) return;
    this.offset.update(value => Math.max(0, value + direction * this.limite));
    void this.cargarNotificaciones();
  }
}