import { Component, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

interface TipoAusencia {
  id: number;
  nombre: string;
  requiere_motivo: boolean;
  modalidad_horas: 'NO_APLICA' | 'OPCIONAL' | 'OBLIGATORIA';
}
interface Solicitud {
  id: number;
  tipo_ausencia: string;
  fecha_inicio: string;
  fecha_fin: string;
  estado_codigo: string;
  version: number;
}
interface Borrador {
  tipo: string;
  fecha_inicio: string;
  fecha_fin: string;
  hora_inicio: string;
  hora_fin: string;
  motivo: string;
}
type Campo = keyof Borrador;

@Component({
  selector: 'app-solicitudes',
  standalone: true,
  imports: [FormsModule, RouterLink],
  template: `
    <h1>Solicitudes de ausencia</h1>
    <section class="card" aria-labelledby="solicitante">
      <h2 id="solicitante">Solicitante</h2>
      @if (identidad(); as persona) {
        <p>Nombre: {{ persona.nombre }}</p>
      } @else {
        <p>{{ cargando() ? 'Cargando identidad…' : 'No se ha podido obtener la identidad del empleado.' }}</p>
      }
    </section>
    @if (errorCarga()) { <p class="error" role="alert">{{ errorCarga() }}</p> }
    <button type="button" class="secondary" (click)="cargar()" [disabled]="cargando() || enviando()">Actualizar</button>

    <form novalidate (ngSubmit)="enviar()">
      <p>Los campos con * son obligatorios.</p>
      <label class="field">Tipo de ausencia <span aria-hidden="true">*</span>
        <select name="tipo" required [ngModel]="borrador().tipo" (ngModelChange)="cambiar('tipo', $event)" (blur)="marcar('tipo')">
          <option value="">Seleccione un tipo</option>
          @for (tipo of tipos(); track tipo.id) { <option [value]="tipo.id">{{ tipo.nombre }}</option> }
        </select>
      </label>
      @if (visible('tipo') && !seleccionado()) { <p class="error">Seleccione el tipo de ausencia.</p> }
      <label class="field">Fecha de inicio <span aria-hidden="true">*</span>
        <input name="fecha_inicio" type="date" required [ngModel]="borrador().fecha_inicio" (ngModelChange)="cambiar('fecha_inicio', $event)" (blur)="marcar('fecha_inicio')">
      </label>
      @if (visible('fecha_inicio') && !borrador().fecha_inicio) { <p class="error">La fecha de inicio es obligatoria.</p> }
      <label class="field">Fecha de fin <span aria-hidden="true">*</span>
        <input name="fecha_fin" type="date" required [ngModel]="borrador().fecha_fin" (ngModelChange)="cambiar('fecha_fin', $event)" (blur)="marcar('fecha_fin')">
      </label>
      @if (visible('fecha_fin') && !borrador().fecha_fin) { <p class="error">La fecha de fin es obligatoria.</p> }
      @if ((visible('fecha_inicio') || visible('fecha_fin')) && fechasInvertidas()) { <p class="error">La fecha final debe ser igual o posterior a la inicial</p> }
      <label class="field">Hora de inicio (si aplica)
        @if (seleccionado()?.modalidad_horas === 'OBLIGATORIA') { <span aria-hidden="true">*</span> }
        <input name="hora_inicio" type="time" step="1" [required]="seleccionado()?.modalidad_horas === 'OBLIGATORIA'" [disabled]="seleccionado()?.modalidad_horas === 'NO_APLICA'" [ngModel]="borrador().hora_inicio" (ngModelChange)="cambiar('hora_inicio', $event)" (blur)="marcar('hora_inicio')">
      </label>
      <label class="field">Hora de fin (si aplica)
        @if (seleccionado()?.modalidad_horas === 'OBLIGATORIA') { <span aria-hidden="true">*</span> }
        <input name="hora_fin" type="time" step="1" [required]="seleccionado()?.modalidad_horas === 'OBLIGATORIA'" [disabled]="seleccionado()?.modalidad_horas === 'NO_APLICA'" [ngModel]="borrador().hora_fin" (ngModelChange)="cambiar('hora_fin', $event)" (blur)="marcar('hora_fin')">
      </label>
      @if ((visible('hora_inicio') || visible('hora_fin') || visible('tipo')) && errorHoras()) { <p class="error">{{ errorHoras() }}</p> }
      <label class="field">Motivo u observación del permiso (si aplica al tipo seleccionado)
        @if (seleccionado()?.requiere_motivo) { <span aria-hidden="true">*</span> }
        <input name="motivo" type="text" maxlength="5000" [required]="seleccionado()?.requiere_motivo === true" [ngModel]="borrador().motivo" (ngModelChange)="cambiar('motivo', $event)" (blur)="marcar('motivo')">
      </label>
      <p>Máximo 5000 caracteres.</p>
      @if ((visible('motivo') || visible('tipo')) && seleccionado()?.requiere_motivo && !borrador().motivo.trim()) { <p class="error">Este tipo de ausencia requiere motivo u observación</p> }
      @if (visible('motivo') && borrador().motivo.trim().length > 5000) { <p class="error">El motivo u observación no puede superar los 5000 caracteres.</p> }
      <div class="actions"><button type="submit" [disabled]="enviando() || cargando() || !identidad() || !tipos().length">{{ enviando() ? 'Enviando…' : 'Enviar solicitud' }}</button></div>
      @if (mensaje()) { <p class="error" role="alert">{{ mensaje() }}</p> }
      @if (confirmacion()) { <p class="success" role="status">{{ confirmacion() }}</p> }
    </form>

    <section class="card" aria-labelledby="historial">
      <h2 id="historial">Historial de solicitudes</h2>
      @if (errorListado()) { <p class="error" role="alert">{{ errorListado() }}</p> }
      @if (solicitudes().length) {
        <table>
          <thead><tr><th>Solicitud</th><th>Fechas</th><th>Estado</th><th>Seguimiento</th></tr></thead>
          <tbody>
            @for (solicitud of solicitudes(); track solicitud.id) {
              <tr><td>{{ solicitud.tipo_ausencia }} #{{ solicitud.id }}</td><td>{{ solicitud.fecha_inicio }} - {{ solicitud.fecha_fin }}</td><td><span class="badge">{{ solicitud.estado_codigo }}</span></td><td><button type="button" [routerLink]="['/solicitudes', solicitud.id]">Consultar detalle e historial</button></td></tr>
            }
          </tbody>
        </table>
      } @else if (!cargando() && !errorListado()) { <p>No hay solicitudes registradas.</p> }
    </section>
  `
})
export class SolicitudesComponent {
  readonly identidad = signal<{ id: number; nombre: string } | null>(null);
  readonly tipos = signal<TipoAusencia[]>([]);
  readonly solicitudes = signal<Solicitud[]>([]);
  readonly cargando = signal(false);
  readonly enviando = signal(false);
  readonly errorCarga = signal('');
  readonly errorListado = signal('');
  readonly borrador = signal<Borrador>(this.vacio());
  readonly tocados = signal<Campo[]>([]);
  readonly intentado = signal(false);
  readonly mensaje = signal('');
  readonly confirmacion = signal('');
  readonly seleccionado = computed(() => this.tipos().find(t => t.id === Number(this.borrador().tipo)));
  readonly fechasInvertidas = computed(() => {
    const b = this.borrador();
    return !!b.fecha_inicio && !!b.fecha_fin && b.fecha_fin < b.fecha_inicio;
  });
  readonly errorHoras = computed(() => {
    const b = this.borrador();
    const modalidad = this.seleccionado()?.modalidad_horas;
    if (modalidad === 'NO_APLICA' && (b.hora_inicio || b.hora_fin)) return 'Este tipo de ausencia no admite horas';
    if (Boolean(b.hora_inicio) !== Boolean(b.hora_fin)) return 'Las horas deben proporcionarse juntas';
    if (modalidad === 'OBLIGATORIA' && !b.hora_inicio) return 'Este tipo de ausencia requiere horas';
    if (b.fecha_inicio && b.fecha_fin && b.hora_inicio && b.hora_fin && `${b.fecha_fin}T${this.normalizarHora(b.hora_fin)}` <= `${b.fecha_inicio}T${this.normalizarHora(b.hora_inicio)}`) return 'El final debe ser posterior al inicio';
    return '';
  });

  constructor() { void this.cargar(); }

  async cargar(): Promise<void> {
    if (this.cargando() || this.enviando()) return;
    this.cargando.set(true);
    this.identidad.set(null);
    this.tipos.set([]);
    this.solicitudes.set([]);
    this.errorCarga.set('');
    this.errorListado.set('');
    try {
      // La identidad se obtiene de la sesión, nunca del formulario.
      const persona = await this.consultar<{ id: number; nombre: string }>('/api/empleado/identidad');
      this.identidad.set(persona);
      await Promise.all([
        this.cargarCatalogo(),
        this.cargarListado()
      ]);
    } catch (error) {
      const texto = this.textoError(error);
      this.errorCarga.set(texto);
      this.errorListado.set(texto);
    } finally {
      this.cargando.set(false);
    }
  }

  private async cargarCatalogo(): Promise<void> {
    try {
      const tipos = await this.consultarPaginas<TipoAusencia>('/api/empleado/tipos-ausencia');
      this.tipos.set(tipos);
      if (!tipos.length) this.errorCarga.set('No hay tipos de ausencia activos disponibles.');
      if (this.seleccionado()?.modalidad_horas === 'NO_APLICA') {
        this.borrador.update(b => ({ ...b, hora_inicio: '', hora_fin: '' }));
      }
    } catch (error) {
      this.tipos.set([]);
      this.errorCarga.set(this.textoError(error));
    }
  }

  private async cargarListado(): Promise<void> {
    this.errorListado.set('');
    try {
      this.solicitudes.set(await this.consultarPaginas<Solicitud>('/api/empleado/solicitudes'));
    } catch (error) {
      this.solicitudes.set([]);
      this.errorListado.set(this.textoError(error));
    }
  }

  cambiar(campo: Campo, valor: string): void {
    this.borrador.update(b => ({ ...b, [campo]: String(valor ?? '') }));
    if (campo === 'tipo' && this.seleccionado()?.modalidad_horas === 'NO_APLICA') {
      this.borrador.update(b => ({ ...b, hora_inicio: '', hora_fin: '' }));
    }
    this.marcar(campo);
    this.mensaje.set('');
    this.confirmacion.set('');
  }

  marcar(campo: Campo): void {
    this.tocados.update(campos => campos.includes(campo) ? campos : [...campos, campo]);
  }
  visible(campo: Campo): boolean { return this.intentado() || this.tocados().includes(campo); }

  async enviar(): Promise<void> {
    if (this.enviando() || this.cargando()) return;
    this.intentado.set(true);
    this.mensaje.set('');
    this.confirmacion.set('');
    const b = this.borrador();
    const tipo = this.seleccionado();
    let error = '';
    if (!this.identidad()) error = 'No se ha podido obtener la identidad del empleado. Actualice la sesión.';
    else if (!tipo) error = 'Seleccione el tipo de ausencia.';
    else if (!b.fecha_inicio) error = 'La fecha de inicio es obligatoria.';
    else if (!b.fecha_fin) error = 'La fecha de fin es obligatoria.';
    else if (!this.fechaValida(b.fecha_inicio) || !this.fechaValida(b.fecha_fin)) error = 'Introduzca fechas válidas.';
    else if (this.fechasInvertidas()) error = 'La fecha final debe ser igual o posterior a la inicial';
    else if (this.errorHoras()) error = this.errorHoras();
    else if ((b.hora_inicio && !this.horaValida(b.hora_inicio)) || (b.hora_fin && !this.horaValida(b.hora_fin))) error = 'Introduzca horas locales válidas, sin zona horaria.';
    else if (tipo.requiere_motivo && !b.motivo.trim()) error = 'Este tipo de ausencia requiere motivo u observación';
    else if (b.motivo.trim().length > 5000) error = 'El motivo u observación no puede superar los 5000 caracteres.';
    if (error || !tipo) {
      this.mensaje.set(error);
      return;
    }
    this.enviando.set(true);
    try {
      const resultado = await this.consultar<Solicitud>('/api/empleado/solicitudes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tipo_ausencia_id: tipo.id,
          origen: 'PORTAL',
          fecha_inicio: b.fecha_inicio,
          fecha_fin: b.fecha_fin,
          hora_inicio: b.hora_inicio ? this.normalizarHora(b.hora_inicio) : null,
          hora_fin: b.hora_fin ? this.normalizarHora(b.hora_fin) : null,
          motivo: b.motivo.trim() || null
        })
      });
      this.confirmacion.set(`Solicitud #${resultado.id} registrada para revisión y aprobación. Estado: ${resultado.estado_codigo}.`);
      this.borrador.set(this.vacio());
      this.tocados.set([]);
      this.intentado.set(false);
      await this.cargarListado();
    } catch (error) {
      this.mensaje.set(this.textoError(error));
    } finally {
      this.enviando.set(false);
    }
  }

  private async consultarPaginas<T>(ruta: string): Promise<T[]> {
    const filas: T[] = [];
    for (let offset = 0; ; offset += 100) {
      const pagina = await this.consultar<T[]>(`${ruta}?limit=100&offset=${offset}`);
      filas.push(...pagina);
      if (pagina.length < 100) return filas;
    }
  }

  private async consultar<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
    const respuesta = await fetch(ruta, { ...opciones, credentials: 'same-origin', cache: 'no-store' });
    const datos: unknown = await respuesta.json().catch(() => null);
    if (!respuesta.ok) {
      const detalle = datos && typeof datos === 'object' && 'detail' in datos ? datos.detail : null;
      if (typeof detalle === 'string') throw new Error(detalle);
      if (Array.isArray(detalle)) {
        const mensajes = detalle.map(item => item && typeof item.msg === 'string' ? item.msg : '').filter(Boolean);
        if (mensajes.length) throw new Error(mensajes.join(' '));
      }
      throw new Error(`No se pudo completar la operación (${respuesta.status}).`);
    }
    if (datos === null) throw new Error('La API devolvió una respuesta no válida.');
    return datos as T;
  }

  private textoError(error: unknown): string {
    return error instanceof Error ? error.message : 'No se pudo contactar con la API. Inténtelo de nuevo.';
  }
  private fechaValida(fecha: string): boolean {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(fecha) || fecha.startsWith('0000')) return false;
    const date = new Date(`${fecha}T00:00:00Z`);
    return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === fecha;
  }
  private horaValida(hora: string): boolean { return /^(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$/.test(hora); }
  private vacio(): Borrador { return { tipo: '', fecha_inicio: '', fecha_fin: '', hora_inicio: '', hora_fin: '', motivo: '' }; }
  private normalizarHora(hora: string): string { return hora.length === 5 ? `${hora}:00` : hora; }
}