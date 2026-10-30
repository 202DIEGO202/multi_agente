import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AdminApi, ApiError, mensajeError } from './admin-api';

type FlujoCodigo = 'JEFE' | 'JEFE_TH' | 'TH';
type Estado = 'ACTIVO' | 'INACTIVO';
type Modalidad = 'NO_APLICA' | 'OPCIONAL' | 'OBLIGATORIA';
interface TipoAusencia {
  id: number;
  nombre: string;
  estado: Estado;
  flujo: FlujoCodigo;
  requiere_motivo: boolean;
  modalidad_horas: Modalidad;
  version: number;
}
interface PasoFlujo { codigo: FlujoCodigo; activo: boolean; orden: number; rol_codigo: string; requiere_validacion: boolean; }

@Component({
  selector: 'app-tipos-ausencia',
  standalone: true,
  imports: [FormsModule],
  template: `
    <h1>Administración de tipos de ausencia</h1>
    @if (api.autenticado()) {
      <button type="button" (click)="api.cerrarSesion()">Cerrar sesión</button>
      @if (error()) { <p role="alert">{{ error() }}</p> }
      @if (mensaje()) { <p role="status">{{ mensaje() }}</p> }
      @if (ocupado()) { <p role="status">Cargando…</p> }
      @if (permitido()) {
        <section class="card">
          <h2>Catálogo de tipos de ausencia</h2>
          <button type="button" (click)="actualizar()" [disabled]="ocupado()">Actualizar</button>
          <button type="button" (click)="nuevo()" [disabled]="ocupado()">Nuevo tipo de ausencia</button>
          @for (tipo of tipos(); track tipo.id) {
            <article class="card">
              <p>Tipo: {{ tipo.nombre }} | Estado: {{ tipo.estado === 'ACTIVO' ? 'Activo' : 'Inactivo' }} | Flujo: {{ etiquetaFlujo(tipo.flujo) }}</p>
              <button type="button" (click)="editar(tipo.id)" [disabled]="ocupado()">Editar</button>
            </article>
          } @empty { @if (!ocupado()) { <p>No hay tipos de ausencia en esta página.</p> } }
          <button type="button" (click)="actualizar(-50)" [disabled]="ocupado() || offset() === 0">Anterior</button>
          <button type="button" (click)="actualizar(50)" [disabled]="ocupado() || tipos().length < 50">Siguiente</button>
        </section>
        <section class="card">
          <h2>{{ editado() ? 'Editar tipo de ausencia' : 'Nuevo tipo de ausencia' }}</h2>
          <form (ngSubmit)="guardar()">
            <label for="tipo-nombre">Nombre del tipo de ausencia</label>
            <input id="tipo-nombre" name="nombre" required maxlength="150" [disabled]="ocupado()"
              [ngModel]="nombre()" (ngModelChange)="nombre.set($event)">
            @if (!nombre().trim()) { <p>El nombre es obligatorio.</p> }
            <label for="tipo-estado">Estado del tipo</label>
            <select id="tipo-estado" name="estado" required [disabled]="ocupado()"
              [ngModel]="estado()" (ngModelChange)="estado.set($event)">
              <option value="ACTIVO">Activo</option><option value="INACTIVO">Inactivo</option>
            </select>
            <label for="tipo-flujo">Flujo de aprobación</label>
            <select id="tipo-flujo" name="flujo" required [disabled]="ocupado()"
              [ngModel]="flujo()" (ngModelChange)="flujo.set($event)">
              <option value="" disabled>Selecciona un flujo</option>
              @for (codigo of flujosDisponibles(); track codigo) { <option [value]="codigo">{{ etiquetaFlujo(codigo) }}</option> }
            </select>
            @if (!flujoValido()) { <p>Selecciona un flujo activo configurado en el servidor.</p> }
            <label for="tipo-motivo">
              <input id="tipo-motivo" name="requiereMotivo" type="checkbox" [disabled]="ocupado()"
                [ngModel]="requiereMotivo()" (ngModelChange)="requiereMotivo.set($event)">
              Motivo u observación obligatorio
            </label>
            <label for="tipo-horas">Modalidad de horas</label>
            <select id="tipo-horas" name="modalidadHoras" required [disabled]="ocupado()"
              [ngModel]="modalidadHoras()" (ngModelChange)="modalidadHoras.set($event)">
              <option value="NO_APLICA">No aplica</option>
              <option value="OPCIONAL">Opcional</option>
              <option value="OBLIGATORIA">Obligatoria</option>
            </select>
            <p>La API valida estas reglas. Las solicitudes existentes conservan sus reglas originales.</p>
            <button type="submit" [disabled]="ocupado() || !nombre().trim() || !flujoValido()">Guardar tipo de ausencia</button>
            @if (editado()) { <button type="button" (click)="nuevo()" [disabled]="ocupado()">Cancelar edición</button> }
          </form>
        </section>
      }
    }
  `
})
export class TiposAusenciaComponent implements OnInit {
  readonly api = inject(AdminApi);
  readonly tipos = signal<TipoAusencia[]>([]);
  readonly flujosDisponibles = signal<FlujoCodigo[]>([]);
  readonly permitido = signal(false);
  readonly ocupado = signal(false);
  readonly error = signal('');
  readonly mensaje = signal('');
  readonly offset = signal(0);
  readonly editado = signal<TipoAusencia | null>(null);
  readonly nombre = signal('');
  readonly estado = signal<Estado>('ACTIVO');
  readonly flujo = signal<FlujoCodigo | ''>('');
  readonly requiereMotivo = signal(false);
  readonly modalidadHoras = signal<Modalidad>('OPCIONAL');
  readonly flujoValido = computed(() => this.flujosDisponibles().some(codigo => codigo === this.flujo()));

  etiquetaFlujo(codigo: string): string {
    return codigo === 'JEFE' ? 'Jefe inmediato' : codigo === 'JEFE_TH' ? 'Jefe inmediato > Talento Humano' : codigo === 'TH' ? 'Talento Humano' : codigo;
  }

  ngOnInit(): void { void this.iniciar(); }

  private async iniciar(): Promise<void> {
    this.ocupado.set(true);
    try {
      const actor = await this.api.cargarIdentidad();
      this.permitido.set(actor.roles.includes('TALENTO_HUMANO'));
      if (!this.permitido()) throw new Error('Solo Talento Humano puede administrar el catálogo.');
      await this.cargar();
    } catch (error) { this.error.set(mensajeError(error)); }
    finally { this.ocupado.set(false); }
  }

  private async cargar(): Promise<void> {
    const pasos = await this.api.request<PasoFlujo[]>('flujos');
    const codigos: FlujoCodigo[] = ['JEFE', 'JEFE_TH', 'TH'];
    this.flujosDisponibles.set(codigos.filter(codigo => pasos.some(paso => paso.codigo === codigo && paso.activo)));
    this.tipos.set(await this.api.request<TipoAusencia[]>(`tipos-ausencia?limit=50&offset=${this.offset()}`));
  }

  nuevo(): void {
    this.editado.set(null);
    this.nombre.set('');
    this.estado.set('ACTIVO');
    this.flujo.set('');
    this.requiereMotivo.set(false);
    this.modalidadHoras.set('OPCIONAL');
  }

  async actualizar(desplazamiento = 0): Promise<void> {
    if (this.ocupado() || !this.permitido()) return;
    this.ocupado.set(true);
    this.offset.set(Math.max(0, this.offset() + desplazamiento));
    this.error.set('');
    this.mensaje.set('');
    this.tipos.set([]);
    this.nuevo();
    try { await this.cargar(); }
    catch (error) { this.error.set(mensajeError(error)); }
    finally { this.ocupado.set(false); }
  }

  async editar(id: number): Promise<void> {
    if (this.ocupado()) return;
    this.ocupado.set(true);
    this.error.set('');
    this.mensaje.set('');
    this.nuevo();
    try {
      const tipo = await this.api.request<TipoAusencia>(`tipos-ausencia/${id}`);
      this.editado.set(tipo);
      this.nombre.set(tipo.nombre);
      this.estado.set(tipo.estado);
      this.flujo.set(tipo.flujo);
      this.requiereMotivo.set(tipo.requiere_motivo);
      this.modalidadHoras.set(tipo.modalidad_horas);
    } catch (error) { this.error.set(mensajeError(error)); }
    finally { this.ocupado.set(false); }
  }

  async guardar(): Promise<void> {
    if (this.ocupado() || !this.permitido() || !this.nombre().trim() || !this.flujoValido()) return;
    this.ocupado.set(true);
    this.error.set('');
    this.mensaje.set('');
    const anterior = this.editado();
    const cuerpo = {
      nombre: this.nombre().trim(), estado: this.estado(), flujo: this.flujo(),
      requiere_motivo: this.requiereMotivo(), modalidad_horas: this.modalidadHoras(),
      ...(anterior ? { version: anterior.version } : {})
    };
    try {
      await this.api.request(anterior ? `tipos-ausencia/${anterior.id}` : 'tipos-ausencia', anterior ? 'PUT' : 'POST', cuerpo);
      this.nuevo();
      this.mensaje.set('Tipo de ausencia guardado correctamente.');
      await this.cargar();
    } catch (error) {
      this.error.set(mensajeError(error));
      if (error instanceof ApiError && (error.status === 409 || error.status === 404)) {
        this.nuevo();
        this.mensaje.set('No se reintentó el guardado. Selecciona de nuevo el tipo para revisar sus datos actuales.');
        try { await this.cargar(); }
        catch (recarga) { this.error.set(mensajeError(error) + ' ' + mensajeError(recarga)); }
      }
    } finally { this.ocupado.set(false); }
  }
}