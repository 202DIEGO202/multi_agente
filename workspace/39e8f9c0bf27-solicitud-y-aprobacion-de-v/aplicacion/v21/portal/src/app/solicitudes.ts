import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { PortalApi } from './portal-api';

interface OpcionAusencia { id: number; nombre: string; requiere_motivo: boolean; permite_horas: boolean; }
interface Solicitud { id: number; tipo_ausencia: string; fecha_inicio: string; fecha_fin: string; estado: string; estado_codigo: string; ultimo_cambio: string | null; fecha_ultimo_cambio: string | null; }
interface Creada { id: number; estado_codigo: string; version: number; }

// PA-001: registro y seguimiento de solicitudes propias.
@Component({
  selector: 'app-solicitudes',
  standalone: true,
  imports: [FormsModule, RouterLink],
  template: `
    <section>
      <h1>Solicitudes de ausencia</h1>
      @if (error()) { <p class="error" role="alert">{{ error() }}</p> }
      @if (message()) { <p class="success" role="status">{{ message() }}</p> }
      <section class="card" aria-label="Registro de solicitud del empleado">
        <h2>Registrar solicitud</h2>
        <p>Los campos marcados con * son obligatorios.</p>
        @if (cargandoOpciones()) { <p role="status">Cargando opciones para la solicitud…</p> }
        <form (ngSubmit)="enviarSolicitud()" novalidate>
          <label class="field">Tipo de ausencia <span aria-hidden="true">*</span>
            <select name="tipo" required [ngModel]="tipoId()" (ngModelChange)="cambiarTipo($event)" [disabled]="enviando() || cargandoOpciones()">
              <option [ngValue]="null">Seleccione un tipo de ausencia</option>
              @for (opcion of opcionesAusencia(); track opcion.id) { <option [ngValue]="opcion.id">{{ opcion.nombre }}</option> }
            </select>
          </label>
          @if (!cargandoOpciones() && opcionesAusencia().length === 0) { <p>No hay tipos de ausencia disponibles.</p> }
          <label class="field">Fecha de inicio <span aria-hidden="true">*</span>
            <input name="fechaInicio" type="date" required [ngModel]="fechaInicio()" (ngModelChange)="fechaInicio.set($event)" [disabled]="enviando()">
          </label>
          <label class="field">Fecha de fin <span aria-hidden="true">*</span>
            <input name="fechaFin" type="date" required [min]="fechaInicio()" [ngModel]="fechaFin()" (ngModelChange)="fechaFin.set($event)" [disabled]="enviando()">
          </label>
          @if (tipoSeleccionado()?.permite_horas) {
            <label class="field">Hora de inicio (si aplica)
              <input name="horaInicio" type="time" [ngModel]="horaInicio()" (ngModelChange)="horaInicio.set($event)" [disabled]="enviando()">
            </label>
            <label class="field">Hora de fin (si aplica)
              <input name="horaFin" type="time" [ngModel]="horaFin()" (ngModelChange)="horaFin.set($event)" [disabled]="enviando()">
            </label>
          }
          <label class="field">Motivo u observación del permiso (si aplica al tipo seleccionado)
            @if (tipoSeleccionado()?.requiere_motivo) { <span aria-hidden="true">*</span> }
            <input name="motivo" type="text" maxlength="5000" [required]="tipoSeleccionado()?.requiere_motivo ?? false" [ngModel]="motivo()" (ngModelChange)="motivo.set($event)" [disabled]="enviando()">
          </label>
          @if (errorPeriodo()) { <p class="error" role="alert">{{ errorPeriodo() }}</p> }
          <button type="submit" [disabled]="enviando() || cargandoOpciones() || !opcionesAusencia().length">{{ enviando() ? 'Enviando…' : 'Enviar solicitud' }}</button>
        </form>
      </section>
      <section class="card" [attr.aria-busy]="cargandoSolicitudes()">
        <h2>Historial de solicitudes</h2>
        <button class="secondary" type="button" (click)="cargarSolicitudes()" [disabled]="cargandoSolicitudes()">Actualizar solicitudes</button>
        @if (cargandoSolicitudes()) { <p role="status">Cargando solicitudes…</p> }
        @if (errorListado()) { <p class="error" role="alert">{{ errorListado() }}</p> }
        @for (solicitud of solicitudes(); track solicitud.id) {
          <article class="card">
            <p>Solicitud: {{ solicitud.id }} | Tipo de ausencia: {{ solicitud.tipo_ausencia }}</p>
            <p>Fechas: {{ solicitud.fecha_inicio }} - {{ solicitud.fecha_fin }}</p>
            <p>Estado: {{ solicitud.estado || solicitud.estado_codigo }}</p>
            <p>Último cambio: {{ solicitud.ultimo_cambio || 'Sin cambios registrados' }} {{ solicitud.fecha_ultimo_cambio || '' }}</p>
            <a routerLink="/notificaciones" [queryParams]="{ solicitud_id: solicitud.id }">Consultar detalle e historial</a>
          </article>
        } @empty {
          @if (!cargandoSolicitudes() && !errorListado()) { <p>No tiene solicitudes registradas.</p> }
        }
        <nav aria-label="Paginación de solicitudes">
          <button class="secondary" type="button" (click)="pagina(-1)" [disabled]="cargandoSolicitudes() || offset() === 0">Anterior</button>
          <span>Página {{ offset() / limite + 1 }}</span>
          <button class="secondary" type="button" (click)="pagina(1)" [disabled]="cargandoSolicitudes() || solicitudes().length < limite">Siguiente</button>
        </nav>
      </section>
    </section>
  `
})
export class SolicitudesComponent {
  private readonly api = inject(PortalApi);
  readonly opcionesAusencia = signal<OpcionAusencia[]>([]);
  readonly solicitudes = signal<Solicitud[]>([]);
  readonly tipoId = signal<number | null>(null);
  readonly tipoSeleccionado = computed(() => this.opcionesAusencia().find(opcion => opcion.id === this.tipoId()) ?? null);
  readonly fechaInicio = signal('');
  readonly fechaFin = signal('');
  readonly horaInicio = signal('');
  readonly horaFin = signal('');
  readonly motivo = signal('');
  readonly cargandoOpciones = signal(false);
  readonly cargandoSolicitudes = signal(false);
  readonly enviando = signal(false);
  readonly error = signal('');
  readonly errorListado = signal('');
  readonly message = signal('');
  readonly offset = signal(0);
  readonly limite = 50;
  private alive = true;

  readonly errorPeriodo = computed(() => {
    const inicio = this.fechaInicio();
    const fin = this.fechaFin();
    if (inicio && fin && fin < inicio) return 'La fecha de fin no puede preceder a la fecha de inicio';
    if (!this.tipoSeleccionado()?.permite_horas) return '';
    const horaInicio = this.horaInicio();
    const horaFin = this.horaFin();
    if (!!horaInicio !== !!horaFin) return 'Debe proporcionar ambas horas o ninguna';
    if (inicio && fin && horaInicio && `${fin}T${horaFin}` <= `${inicio}T${horaInicio}`) return 'La fecha y hora final deben ser posteriores al inicio';
    return '';
  });

  constructor() {
    inject(DestroyRef).onDestroy(() => { this.alive = false; });
    void this.cargarOpcionesSolicitud();
    void this.cargarSolicitudes();
  }

  cambiarTipo(id: number | null): void {
    this.tipoId.set(id);
    this.horaInicio.set('');
    this.horaFin.set('');
  }

  // Alimenta únicamente el selector del formulario, sin acciones de gestión.
  private async cargarOpcionesSolicitud(): Promise<void> {
    if (this.cargandoOpciones()) return;
    this.cargandoOpciones.set(true);
    this.error.set('');
    this.opcionesAusencia.set([]);
    try {
      const opciones: OpcionAusencia[] = [];
      for (let offset = 0; ; offset += 200) {
        const pagina = await this.api.consultar<OpcionAusencia[]>(`/api/portal/tipos-ausencia?limite=200&offset=${offset}`);
        if (!this.alive) return;
        opciones.push(...pagina);
        if (pagina.length < 200) break;
      }
      this.opcionesAusencia.set(opciones);
    } catch (error) { if (this.alive) this.error.set(this.api.mensaje(error)); }
    finally { this.cargandoOpciones.set(false); }
  }

  async cargarSolicitudes(): Promise<void> {
    if (this.cargandoSolicitudes()) return;
    this.cargandoSolicitudes.set(true);
    this.errorListado.set('');
    this.solicitudes.set([]);
    try {
      const rows = await this.api.consultar<Solicitud[]>(`/api/portal/solicitudes?limite=${this.limite}&offset=${this.offset()}`);
      if (this.alive) this.solicitudes.set(rows);
    } catch (error) { if (this.alive) this.errorListado.set(this.api.mensaje(error)); }
    finally { this.cargandoSolicitudes.set(false); }
  }

  pagina(direction: number): void {
    if (this.cargandoSolicitudes()) return;
    this.offset.update(value => Math.max(0, value + direction * this.limite));
    void this.cargarSolicitudes();
  }

  async enviarSolicitud(): Promise<void> {
    if (this.enviando()) return;
    this.error.set('');
    this.message.set('');
    const tipo = this.tipoSeleccionado();
    const motivo = this.motivo().trim();
    if (!tipo || !this.fechaInicio() || !this.fechaFin()) { this.error.set('Seleccione el tipo de ausencia y ambas fechas.'); return; }
    if (this.errorPeriodo()) { this.error.set(this.errorPeriodo()); return; }
    if (tipo.requiere_motivo && !motivo) { this.error.set('El motivo es obligatorio para este tipo de ausencia'); return; }
    if (motivo.length > 5000) { this.error.set('El motivo no puede superar los 5000 caracteres.'); return; }
    const horaInicio = tipo.permite_horas ? this.horaInicio() : '';
    const horaFin = tipo.permite_horas ? this.horaFin() : '';
    this.enviando.set(true);
    try {
      const creada = await this.api.consultar<Creada>('/api/solicitudes', {
        tipo_ausencia_id: tipo.id,
        fecha_inicio: this.fechaInicio(),
        fecha_fin: this.fechaFin(),
        hora_inicio: horaInicio || null,
        hora_fin: horaFin || null,
        motivo: motivo || null
      });
      if (!this.alive) return;
      this.message.set(`Solicitud ${creada.id} registrada para revisión. Estado: ${creada.estado_codigo}.`);
      this.tipoId.set(null);
      this.fechaInicio.set(''); this.fechaFin.set(''); this.horaInicio.set(''); this.horaFin.set(''); this.motivo.set('');
      this.offset.set(0);
      await this.cargarSolicitudes();
    } catch (error) { if (this.alive) this.error.set(this.api.mensaje(error)); }
    finally { this.enviando.set(false); }
  }
}