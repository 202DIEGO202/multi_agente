import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { PortalAuth } from './auth.service';

interface TipoAusencia { id: number; nombre: string; requiere_motivo: boolean; permite_horas: boolean; }
interface Solicitud { id: number; tipo_ausencia: string; fecha_inicio: string; fecha_fin: string; estado: string; estado_codigo: string; ultimo_cambio: string | null; fecha_ultimo_cambio: string | null; }
interface Creada { id: number; estado_codigo: string; version: number; }

@Component({
  selector: 'app-solicitudes',
  standalone: true,
  imports: [FormsModule, RouterLink],
  template: `
    <section class="page">
      <h1>Solicitud de vacaciones y permisos</h1>
      @if (auth.message()) { <p class="alert" role="alert">{{ auth.message() }}</p> }
      @if (!auth.authenticated()) {
        <section class="card">
          <h2>Acceso del empleado</h2>
          <form (submit)="$event.preventDefault(); acceder(token)">
            <label for="employee-token">Token de empleado</label>
            <input #token id="employee-token" type="password" autocomplete="off" required>
            <button class="btn btn-primary" type="submit">Acceder</button>
          </form>
          <p>La credencial se conserva únicamente en sessionStorage.</p>
        </section>
      } @else {
        <button class="btn" type="button" (click)="cerrar()">Cerrar sesión</button>
        @if (error()) { <p class="alert" role="alert">{{ error() }}</p> }
        @if (message()) { <p class="alert" role="status">{{ message() }}</p> }
        <section class="card">
          <h2>Registrar solicitud</h2>
          @if (cargandoTipos()) { <p role="status">Cargando tipos de ausencia…</p> }
          <form (ngSubmit)="enviarSolicitud()" #form="ngForm">
            <label for="tipo-ausencia">Tipo de ausencia</label>
            <select id="tipo-ausencia" name="tipo" required [ngModel]="tipoId()" (ngModelChange)="cambiarTipo($event)" [disabled]="enviando() || cargandoTipos()">
              <option [ngValue]="null">Seleccione un tipo de ausencia</option>
              @for (tipo of tipos(); track tipo.id) { <option [ngValue]="tipo.id">{{ tipo.nombre }}</option> }
            </select>
            @if (!cargandoTipos() && tipos().length === 0) { <p>No hay tipos de ausencia disponibles.</p> }
            <label for="fecha-inicio">Fecha de inicio</label>
            <input id="fecha-inicio" name="fechaInicio" type="date" required [ngModel]="fechaInicio()" (ngModelChange)="fechaInicio.set($event)" [disabled]="enviando()">
            <label for="fecha-fin">Fecha de fin</label>
            <input id="fecha-fin" name="fechaFin" type="date" required [min]="fechaInicio()" [ngModel]="fechaFin()" (ngModelChange)="fechaFin.set($event)" [disabled]="enviando()">
            @if (tipoSeleccionado()?.permite_horas) {
              <label for="hora-inicio">Hora de inicio</label>
              <input id="hora-inicio" name="horaInicio" type="time" [ngModel]="horaInicio()" (ngModelChange)="horaInicio.set($event)" [disabled]="enviando()">
              <label for="hora-fin">Hora de fin</label>
              <input id="hora-fin" name="horaFin" type="time" [ngModel]="horaFin()" (ngModelChange)="horaFin.set($event)" [disabled]="enviando()">
            }
            <label for="motivo">Motivo u observación{{ tipoSeleccionado()?.requiere_motivo ? ' (obligatorio)' : '' }}</label>
            <textarea id="motivo" name="motivo" maxlength="5000" [required]="tipoSeleccionado()?.requiere_motivo ?? false" [ngModel]="motivo()" (ngModelChange)="motivo.set($event)" [disabled]="enviando()"></textarea>
            <button class="btn btn-primary" type="submit" [disabled]="enviando() || cargandoTipos() || form.invalid || !tipoSeleccionado()">{{ enviando() ? 'Enviando…' : 'Enviar solicitud' }}</button>
          </form>
        </section>
        <section class="card" [attr.aria-busy]="cargandoSolicitudes()">
          <h2>Historial de solicitudes</h2>
          <button class="btn" type="button" (click)="cargarSolicitudes()" [disabled]="cargandoSolicitudes()">Actualizar solicitudes</button>
          @if (cargandoSolicitudes()) { <p role="status">Cargando solicitudes…</p> }
          @if (errorListado()) { <p class="alert" role="alert">{{ errorListado() }}</p> }
          @for (solicitud of solicitudes(); track solicitud.id) {
            <article class="card">
              <p>Solicitud: {{ solicitud.id }} | Tipo de ausencia: {{ solicitud.tipo_ausencia }}</p>
              <p>Fechas: {{ solicitud.fecha_inicio }} - {{ solicitud.fecha_fin }}</p>
              <p>Estado: {{ solicitud.estado || solicitud.estado_codigo }}</p>
              <p>Último cambio: {{ solicitud.ultimo_cambio || 'Sin cambios registrados' }} {{ solicitud.fecha_ultimo_cambio || '' }}</p>
              <a class="btn" routerLink="/notificaciones" [queryParams]="{ solicitud_id: solicitud.id }">Ver detalle e historial</a>
            </article>
          } @empty {
            @if (!cargandoSolicitudes() && !errorListado()) { <p>No tiene solicitudes registradas.</p> }
          }
          <nav aria-label="Paginación de solicitudes">
            <button class="btn" type="button" (click)="pagina(-1)" [disabled]="cargandoSolicitudes() || offset() === 0">Anterior</button>
            <span>Página {{ offset() / limite + 1 }}</span>
            <button class="btn" type="button" (click)="pagina(1)" [disabled]="cargandoSolicitudes() || solicitudes().length < limite">Siguiente</button>
          </nav>
        </section>
      }
    </section>
  `
})
export class Solicitudes {
  readonly auth = inject(PortalAuth);
  readonly tipos = signal<TipoAusencia[]>([]);
  readonly solicitudes = signal<Solicitud[]>([]);
  readonly tipoId = signal<number | null>(null);
  readonly tipoSeleccionado = computed(() => this.tipos().find(tipo => tipo.id === this.tipoId()) ?? null);
  readonly fechaInicio = signal('');
  readonly fechaFin = signal('');
  readonly horaInicio = signal('');
  readonly horaFin = signal('');
  readonly motivo = signal('');
  readonly cargandoTipos = signal(false);
  readonly cargandoSolicitudes = signal(false);
  readonly enviando = signal(false);
  readonly error = signal('');
  readonly errorListado = signal('');
  readonly message = signal('');
  readonly offset = signal(0);
  readonly limite = 50;
  private alive = true;

  constructor() {
    inject(DestroyRef).onDestroy(() => { this.alive = false; });
    if (this.auth.hasToken()) { void this.cargarTipos(); void this.cargarSolicitudes(); }
  }

  acceder(input: HTMLInputElement): void {
    const token = input.value.trim();
    if (!token) return;
    this.auth.start(token);
    input.value = '';
    void this.cargarTipos();
    void this.cargarSolicitudes();
  }

  cerrar(): void { this.tipos.set([]); this.solicitudes.set([]); this.auth.logout(); }
  cambiarTipo(id: number | null): void { this.tipoId.set(id); this.horaInicio.set(''); this.horaFin.set(''); }
  private mensaje(error: unknown): string { return error instanceof Error ? error.message : 'No se pudo completar la operación.'; }

  async cargarTipos(): Promise<void> {
    if (this.cargandoTipos() || !this.auth.hasToken()) return;
    this.cargandoTipos.set(true);
    this.error.set('');
    this.tipos.set([]);
    try {
      const tipos: TipoAusencia[] = [];
      for (let offset = 0; ; offset += 200) {
        const pagina = await this.auth.request<TipoAusencia[]>(`/api/portal/tipos-ausencia?limite=200&offset=${offset}`);
        if (!this.alive || !this.auth.authenticated()) return;
        tipos.push(...pagina);
        if (pagina.length < 200) break;
      }
      this.tipos.set(tipos);
    } catch (error) { if (this.alive && this.auth.authenticated()) this.error.set(this.mensaje(error)); }
    finally { this.cargandoTipos.set(false); }
  }

  async cargarSolicitudes(): Promise<void> {
    if (this.cargandoSolicitudes() || !this.auth.hasToken()) return;
    this.cargandoSolicitudes.set(true);
    this.errorListado.set('');
    this.solicitudes.set([]);
    try {
      const rows = await this.auth.request<Solicitud[]>(`/api/portal/solicitudes?limite=${this.limite}&offset=${this.offset()}`);
      if (this.alive && this.auth.authenticated()) this.solicitudes.set(rows);
    } catch (error) { if (this.alive && this.auth.authenticated()) this.errorListado.set(this.mensaje(error)); }
    finally { this.cargandoSolicitudes.set(false); }
  }

  pagina(direction: number): void {
    if (this.cargandoSolicitudes()) return;
    this.offset.update(value => Math.max(0, value + direction * this.limite));
    void this.cargarSolicitudes();
  }

  async enviarSolicitud(): Promise<void> {
    if (this.enviando() || !this.auth.hasToken()) return;
    this.error.set('');
    this.message.set('');
    const tipo = this.tipoSeleccionado();
    const motivo = this.motivo().trim();
    if (!tipo || !this.fechaInicio() || !this.fechaFin()) { this.error.set('Seleccione el tipo de ausencia y ambas fechas.'); return; }
    if (this.fechaFin() < this.fechaInicio()) { this.error.set('La fecha de fin no puede preceder a la fecha de inicio.'); return; }
    if (tipo.requiere_motivo && !motivo) { this.error.set('El motivo es obligatorio para este tipo de ausencia.'); return; }
    const horaInicio = tipo.permite_horas ? this.horaInicio() : '';
    const horaFin = tipo.permite_horas ? this.horaFin() : '';
    if (!!horaInicio !== !!horaFin) { this.error.set('Debe proporcionar ambas horas o ninguna.'); return; }
    if (horaInicio && `${this.fechaFin()}T${horaFin}` <= `${this.fechaInicio()}T${horaInicio}`) { this.error.set('La fecha y hora final deben ser posteriores al inicio.'); return; }
    this.enviando.set(true);
    try {
      const creada = await this.auth.request<Creada>('/api/solicitudes', 'POST', {
        tipo_ausencia_id: tipo.id,
        fecha_inicio: this.fechaInicio(),
        fecha_fin: this.fechaFin(),
        hora_inicio: horaInicio || null,
        hora_fin: horaFin || null,
        motivo: motivo || null
      });
      if (!this.alive || !this.auth.authenticated()) return;
      this.message.set(`Solicitud ${creada.id} registrada para revisión. Estado: ${creada.estado_codigo}.`);
      this.tipoId.set(null);
      this.fechaInicio.set(''); this.fechaFin.set(''); this.horaInicio.set(''); this.horaFin.set(''); this.motivo.set('');
      this.offset.set(0);
      await this.cargarSolicitudes();
    } catch (error) { if (this.alive && this.auth.authenticated()) this.error.set(this.mensaje(error)); }
    finally { this.enviando.set(false); }
  }
}