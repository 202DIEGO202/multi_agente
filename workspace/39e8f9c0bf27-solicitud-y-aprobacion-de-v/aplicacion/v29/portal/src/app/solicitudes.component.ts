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
    this.identidad.set(null);
    this.tipos.set([]);
    this.errorCarga.set('Las operaciones del empleado requieren una integración de sesión que no está autorizada por el contrato actual del portal.');
    this.errorListado.set('No se ha consultado el historial: no hay un endpoint público autorizado para esta operación.');
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
    this.mensaje.set('La solicitud no se ha enviado: no hay un endpoint público autorizado para esta operación.');
  }

  private vacio(): Borrador { return { tipo: '', fecha_inicio: '', fecha_fin: '', hora_inicio: '', hora_fin: '', motivo: '' }; }
  private normalizarHora(hora: string): string { return hora.length === 5 ? `${hora}:00` : hora; }
}