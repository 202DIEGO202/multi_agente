import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { CrearSolicitud, Empleado, Notificacion, PortalApi, Solicitud, TipoAusencia, estadoVisible, mensajeError } from './portal-api';

interface Formulario {
  tipo_ausencia_id: number | null;
  fecha_inicio: string;
  fecha_fin: string;
  hora_inicio: string;
  hora_fin: string;
  motivo: string;
}
const formularioVacio = (): Formulario => ({ tipo_ausencia_id: null, fecha_inicio: '', fecha_fin: '', hora_inicio: '', hora_fin: '', motivo: '' });

@Component({
  selector: 'app-solicitudes',
  standalone: true,
  imports: [FormsModule, RouterLink, DatePipe],
  template: `
    <h1>Solicitudes de ausencia</h1>
    <div class="actions">
      <button type="button" class="secondary" (click)="cargar()" [disabled]="cargando() || enviando()">Actualizar</button>
      <button type="button" class="secondary" (click)="api.cerrarSesion()">Cerrar sesión</button>
    </div>
    @if (cargando()) { <p role="status">Cargando información…</p> }
    @if (errorCarga()) { <p class="error" role="alert">{{ errorCarga() }}</p> }
    @if (empleado(); as persona) {
      <section class="card">
        <h2>Solicitante</h2>
        <p>Nombre: {{ persona.nombre }}</p>
        <p>Documento: {{ persona.documento }}</p>
        <p>Área: {{ persona.area }}</p>
        <p>Cargo: {{ persona.cargo }}</p>
      </section>
    }
    <section class="card">
      <h2>Crear solicitud</h2>
      <p>Los campos marcados con * son obligatorios. Las reglas dependen del tipo de ausencia activo.</p>
      <form (ngSubmit)="enviar()" novalidate>
        <label class="field">Tipo de ausencia <span aria-label="obligatorio">*</span>
          <select name="tipo_ausencia_id" required [ngModel]="formulario().tipo_ausencia_id"
            (ngModelChange)="seleccionarTipo($event)" [disabled]="!listo() || enviando()">
            <option [ngValue]="null">Seleccione un tipo de ausencia</option>
            @for (tipo of tipos(); track tipo.id) { <option [ngValue]="tipo.id">{{ tipo.nombre }}</option> }
          </select>
        </label>
        <label class="field">Fecha de inicio <span aria-label="obligatorio">*</span>
          <input type="date" name="fecha_inicio" required [ngModel]="formulario().fecha_inicio"
            (ngModelChange)="cambiar('fecha_inicio', $event)" [disabled]="!listo() || enviando()">
        </label>
        <label class="field">Fecha de fin <span aria-label="obligatorio">*</span>
          <input type="date" name="fecha_fin" required [ngModel]="formulario().fecha_fin"
            (ngModelChange)="cambiar('fecha_fin', $event)" [disabled]="!listo() || enviando()">
        </label>
        <label class="field">Hora de inicio (si aplica)
          <input type="time" name="hora_inicio" step="1" [ngModel]="formulario().hora_inicio"
            (ngModelChange)="cambiar('hora_inicio', $event)" [disabled]="!listo() || enviando() || !tipoSeleccionado()?.permite_horas">
        </label>
        <label class="field">Hora de fin (si aplica)
          <input type="time" name="hora_fin" step="1" [ngModel]="formulario().hora_fin"
            (ngModelChange)="cambiar('hora_fin', $event)" [disabled]="!listo() || enviando() || !tipoSeleccionado()?.permite_horas">
        </label>
        @if (tipoSeleccionado(); as tipo) {
          <p>{{ tipo.permite_horas ? 'Puede indicar ambas horas o ninguna.' : 'Este tipo de ausencia no permite horas.' }}</p>
        }
        <label class="field">Motivo u observación del permiso (si aplica al tipo seleccionado)
          @if (tipoSeleccionado()?.requiere_motivo) { <span aria-label="obligatorio">*</span> }
          <input name="motivo" maxlength="4000" [required]="tipoSeleccionado()?.requiere_motivo === true"
            [ngModel]="formulario().motivo" (ngModelChange)="cambiar('motivo', $event)" [disabled]="!listo() || enviando()">
        </label>
        @if (modificado()) {
          @for (mensaje of errores(); track mensaje) { <p class="error" role="alert">{{ mensaje }}</p> }
        }
        @if (errorEnvio()) { <p class="error" role="alert">{{ errorEnvio() }}</p> }
        @if (resultado(); as creada) {
          <div class="success" role="status">
            <p>Solicitud #{{ creada.id }} registrada para revisión y aprobación del flujo correspondiente.</p>
            <p>Estado: {{ estado(creada.estado_codigo) }} · Versión: {{ creada.version }}</p>
            <a [routerLink]="['/solicitudes', creada.id]">Consultar detalle e historial</a>
          </div>
        }
        <button type="submit" [disabled]="!listo() || enviando()">{{ enviando() ? 'Enviando…' : 'Enviar solicitud' }}</button>
      </form>
    </section>
    <section class="card">
      <h2>Historial de solicitudes</h2>
      @if (solicitudes().length === 0 && listo()) { <p>No tiene solicitudes registradas.</p> }
      @if (solicitudes().length > 0) {
        <table>
          <thead><tr><th>Solicitud</th><th>Fechas</th><th>Estado</th><th>Último cambio</th><th>Seguimiento</th></tr></thead>
          <tbody>
            @for (solicitud of solicitudes(); track solicitud.id) {
              <tr>
                <td>#{{ solicitud.id }} · {{ solicitud.tipo_ausencia }}</td>
                <td>{{ solicitud.fecha_inicio }} - {{ solicitud.fecha_fin }}</td>
                <td><span class="badge">{{ estado(solicitud.estado_codigo) }}</span></td>
                <td>{{ (solicitud.actualizado_en || solicitud.creado_en) | date:'dd/MM/yyyy HH:mm' }} · Versión {{ solicitud.version }}</td>
                <td><a [routerLink]="['/solicitudes', solicitud.id]">Consultar detalle e historial</a></td>
              </tr>
            }
          </tbody>
        </table>
      }
      <div class="actions">
        <button type="button" class="secondary" (click)="pagina(-1)" [disabled]="offset() === 0 || cargando()">Anterior</button>
        <span>Página {{ offset() / limite + 1 }}</span>
        <button type="button" class="secondary" (click)="pagina(1)" [disabled]="solicitudes().length < limite || cargando()">Siguiente</button>
      </div>
    </section>
    <section class="card">
      <h2>Notificación de cambio de estado</h2>
      @if (notificaciones().length === 0 && listo()) { <p>No hay avisos de cambio de estado.</p> }
      @for (aviso of notificaciones(); track aviso.id) {
        <p>
          Solicitud #{{ aviso.solicitud_id }} · Nuevo estado: {{ estado(aviso.estado_nuevo) }}
          · {{ aviso.creado_en | date:'dd/MM/yyyy HH:mm' }}
          @if (!aviso.leida_en) { <span class="badge">Sin leer</span> }
          <a [routerLink]="['/solicitudes', aviso.solicitud_id]">Consultar detalle e historial</a>
        </p>
      }
    </section>
  `
})
export class SolicitudesComponent implements OnInit, OnDestroy {
  readonly api = inject(PortalApi);
  readonly empleado = signal<Empleado | null>(null);
  readonly tipos = signal<TipoAusencia[]>([]);
  readonly solicitudes = signal<Solicitud[]>([]);
  readonly notificaciones = signal<Notificacion[]>([]);
  readonly formulario = signal<Formulario>(formularioVacio());
  readonly modificado = signal(false);
  readonly listo = signal(false);
  readonly cargando = signal(false);
  readonly enviando = signal(false);
  readonly errorCarga = signal('');
  readonly errorEnvio = signal('');
  readonly resultado = signal<Solicitud | null>(null);
  readonly offset = signal(0);
  readonly limite = 20;
  readonly estado = estadoVisible;
  private temporizador?: ReturnType<typeof setInterval>;
  private destruido = false;
  readonly tipoSeleccionado = computed(() => this.tipos().find(tipo => tipo.id === this.formulario().tipo_ausencia_id));
  readonly errores = computed(() => {
    const datos = this.formulario();
    const tipo = this.tipoSeleccionado();
    const mensajes: string[] = [];
    if (!tipo) mensajes.push('Seleccione un tipo de ausencia activo');
    if (!datos.fecha_inicio) mensajes.push('La fecha de inicio es obligatoria.');
    if (!datos.fecha_fin) mensajes.push('La fecha de fin es obligatoria.');
    if (datos.fecha_inicio && datos.fecha_fin && datos.fecha_fin < datos.fecha_inicio) mensajes.push('La fecha final debe ser igual o posterior a la inicial');
    if (!!datos.hora_inicio !== !!datos.hora_fin) mensajes.push('Indique ambas horas o ninguna');
    if (datos.hora_inicio && datos.hora_fin && datos.fecha_inicio && datos.fecha_fin) {
      const inicio = new Date(`${datos.fecha_inicio}T${datos.hora_inicio}`).getTime();
      const fin = new Date(`${datos.fecha_fin}T${datos.hora_fin}`).getTime();
      if (inicio >= fin) mensajes.push('El intervalo horario debe ser positivo');
    }
    if (tipo && !tipo.permite_horas && (datos.hora_inicio || datos.hora_fin)) mensajes.push('Este tipo de ausencia no permite horas');
    if (tipo?.requiere_motivo && !datos.motivo.trim()) mensajes.push('El tipo de ausencia requiere motivo u observación');
    if (datos.motivo.trim().length > 4000) mensajes.push('El motivo debe tener como máximo 4000 caracteres.');
    return mensajes;
  });

  ngOnInit(): void {
    void this.cargar();
    this.temporizador = setInterval(() => {
      if (this.listo() && !this.enviando() && !this.cargando()) void this.cargar();
    }, 30000);
  }
  ngOnDestroy(): void {
    this.destruido = true;
    if (this.temporizador) clearInterval(this.temporizador);
  }

  cambiar(campo: 'fecha_inicio' | 'fecha_fin' | 'hora_inicio' | 'hora_fin' | 'motivo', valor: string): void {
    this.formulario.update(datos => ({ ...datos, [campo]: valor || '' }));
    this.modificado.set(true);
    this.errorEnvio.set('');
    this.resultado.set(null);
  }

  seleccionarTipo(id: number | null): void {
    const tipo = this.tipos().find(item => item.id === id);
    this.formulario.update(datos => ({ ...datos, tipo_ausencia_id: id,
      hora_inicio: tipo?.permite_horas ? datos.hora_inicio : '',
      hora_fin: tipo?.permite_horas ? datos.hora_fin : '' }));
    this.modificado.set(true);
    this.errorEnvio.set('');
    this.resultado.set(null);
  }

  async cargar(): Promise<void> {
    if (this.cargando()) return;
    this.cargando.set(true);
    this.errorCarga.set('');
    try {
      const [persona, tipos, solicitudes, avisos] = await Promise.all([
        this.api.peticion<Empleado>('/api/portal/me'),
        this.api.peticion<TipoAusencia[]>('/api/portal/tipos-ausencia'),
        this.api.peticion<Solicitud[]>(`/api/portal/solicitudes?limite=${this.limite}&offset=${this.offset()}`),
        this.api.peticion<Notificacion[]>('/api/portal/notificaciones?limite=50&offset=0')
      ]);
      if (this.destruido) return;
      this.empleado.set(persona);
      this.tipos.set(tipos);
      this.solicitudes.set(solicitudes);
      this.notificaciones.set(avisos);
      this.listo.set(true);
    } catch (error) {
      if (!this.destruido) this.errorCarga.set(mensajeError(error));
    } finally {
      if (!this.destruido) this.cargando.set(false);
    }
  }

  pagina(direccion: number): void {
    if (this.cargando()) return;
    this.offset.update(valor => Math.max(0, valor + direccion * this.limite));
    void this.cargar();
  }

  async enviar(): Promise<void> {
    if (this.enviando() || !this.listo()) return;
    this.modificado.set(true);
    this.errorEnvio.set('');
    this.resultado.set(null);
    if (this.errores().length > 0) return;
    const datos = this.formulario();
    const cuerpo: CrearSolicitud = {
      tipo_ausencia_id: datos.tipo_ausencia_id!,
      fecha_inicio: datos.fecha_inicio,
      fecha_fin: datos.fecha_fin,
      hora_inicio: datos.hora_inicio || null,
      hora_fin: datos.hora_fin || null,
      motivo: datos.motivo.trim() || null,
      origen: 'PORTAL'
    };
    this.enviando.set(true);
    try {
      const creada = await this.api.peticion<Solicitud>('/api/portal/solicitudes', { method: 'POST', body: JSON.stringify(cuerpo) });
      if (this.destruido) return;
      this.resultado.set(creada);
      this.formulario.set(formularioVacio());
      this.modificado.set(false);
      this.offset.set(0);
      await this.cargar();
    } catch (error) {
      if (!this.destruido) this.errorEnvio.set(mensajeError(error));
    } finally {
      if (!this.destruido) this.enviando.set(false);
    }
  }
}