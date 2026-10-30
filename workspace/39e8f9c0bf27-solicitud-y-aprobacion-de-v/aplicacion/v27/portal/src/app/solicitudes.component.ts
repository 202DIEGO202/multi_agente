import { Component, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

interface Borrador {
  tipo: string;
  fecha_inicio: string;
  fecha_fin: string;
  hora_inicio: string;
  hora_fin: string;
  motivo: string;
}

type Campo = keyof Borrador;

// Registro y seguimiento de solicitudes del empleado.
@Component({
  selector: 'app-solicitudes',
  standalone: true,
  imports: [FormsModule],
  template: `
    <h1>Solicitudes de ausencia</h1>
    <p class="alert" role="status">El contrato disponible no ofrece operaciones públicas para identificar al solicitante, obtener los tipos disponibles, registrar solicitudes ni consultar su historial. Puede completar un borrador en esta pantalla, pero no enviarlo. El borrador no se guarda al salir.</p>

    <section class="card" aria-labelledby="solicitante">
      <h2 id="solicitante">Solicitante</h2>
      <p>No disponible: no existe una consulta pública de identidad del empleado.</p>
    </section>

    <form novalidate (ngSubmit)="enviar()">
      <p>Los campos con * son obligatorios.</p>
      <label class="field">Tipo de ausencia <span aria-hidden="true">*</span>
        <select name="tipo" required [ngModel]="borrador().tipo" (ngModelChange)="cambiar('tipo', $event)" (blur)="marcar('tipo')" aria-describedby="reglas-tipo">
          <option value="">Seleccione un tipo</option>
          @for (opcion of opcionesAusencia; track opcion) {
            <option [value]="opcion">{{ opcion }}</option>
          }
        </select>
      </label>
      <p id="reglas-tipo">Seleccione la ausencia que desea solicitar. Estas opciones solo permiten completar el borrador; las reglas de motivo y horas del tipo seleccionado no están disponibles.</p>
      @if (visible('tipo') && !borrador().tipo) {
        <p class="error">Seleccione el tipo de ausencia.</p>
      }

      <label class="field">Fecha de inicio <span aria-hidden="true">*</span>
        <input name="fecha_inicio" type="date" required [ngModel]="borrador().fecha_inicio" (ngModelChange)="cambiar('fecha_inicio', $event)" (blur)="marcar('fecha_inicio')">
      </label>
      @if (visible('fecha_inicio') && !borrador().fecha_inicio) {
        <p class="error">La fecha de inicio es obligatoria.</p>
      }

      <label class="field">Fecha de fin <span aria-hidden="true">*</span>
        <input name="fecha_fin" type="date" required [ngModel]="borrador().fecha_fin" (ngModelChange)="cambiar('fecha_fin', $event)" (blur)="marcar('fecha_fin')">
      </label>
      @if (visible('fecha_fin') && !borrador().fecha_fin) {
        <p class="error">La fecha de fin es obligatoria.</p>
      }
      @if ((visible('fecha_inicio') || visible('fecha_fin')) && fechasInvertidas()) {
        <p class="error">La fecha final debe ser igual o posterior a la inicial</p>
      }

      <label class="field">Hora de inicio (si aplica)
        <input name="hora_inicio" type="time" step="1" [ngModel]="borrador().hora_inicio" (ngModelChange)="cambiar('hora_inicio', $event)" (blur)="marcar('hora_inicio')">
      </label>
      <label class="field">Hora de fin (si aplica)
        <input name="hora_fin" type="time" step="1" [ngModel]="borrador().hora_fin" (ngModelChange)="cambiar('hora_fin', $event)" (blur)="marcar('hora_fin')">
      </label>
      @if ((visible('hora_inicio') || visible('hora_fin')) && horasIncompletas()) {
        <p class="error">Las horas deben proporcionarse juntas</p>
      }
      @if ((visible('hora_inicio') || visible('hora_fin') || visible('fecha_fin')) && finalNoPosterior()) {
        <p class="error">El final debe ser posterior al inicio</p>
      }

      <label class="field">Motivo u observación del permiso (si aplica al tipo seleccionado)
        <input name="motivo" type="text" maxlength="5000" [ngModel]="borrador().motivo" (ngModelChange)="cambiar('motivo', $event)" (blur)="marcar('motivo')">
      </label>
      <p>Máximo 5000 caracteres. La obligatoriedad depende de las reglas del tipo seleccionado, actualmente no disponibles.</p>
      @if (visible('motivo') && borrador().motivo.trim().length > 5000) {
        <p class="error">El motivo u observación no puede superar los 5000 caracteres.</p>
      }
      <div class="actions">
        <button type="submit">Enviar solicitud</button>
      </div>
      @if (mensaje()) {
        <p class="error" role="alert">{{ mensaje() }}</p>
      }
    </form>

    <section class="card" aria-labelledby="historial">
      <h2 id="historial">Historial de solicitudes</h2>
      <p>No disponible: el contrato no permite consultar solicitudes del empleado desde el portal. No se han cargado registros.</p>
      <button type="button" disabled aria-describedby="detalle-bloqueado">Consultar detalle e historial</button>
      <p id="detalle-bloqueado">Se necesita una solicitud obtenida mediante una consulta pública autorizada para abrir su detalle.</p>
    </section>
  `
})
export class SolicitudesComponent {
  readonly opcionesAusencia: readonly string[] = ['Vacaciones', 'Permiso médico', 'Permiso personal', 'Otro permiso'];
  readonly borrador = signal<Borrador>({ tipo: '', fecha_inicio: '', fecha_fin: '', hora_inicio: '', hora_fin: '', motivo: '' });
  readonly tocados = signal<Campo[]>([]);
  readonly intentado = signal(false);
  readonly mensaje = signal('');

  readonly fechasInvertidas = computed(() => {
    const b = this.borrador();
    return !!b.fecha_inicio && !!b.fecha_fin && b.fecha_fin < b.fecha_inicio;
  });
  readonly horasIncompletas = computed(() => {
    const b = this.borrador();
    return Boolean(b.hora_inicio) !== Boolean(b.hora_fin);
  });
  readonly finalNoPosterior = computed(() => {
    const b = this.borrador();
    if (!b.fecha_inicio || !b.fecha_fin || !b.hora_inicio || !b.hora_fin) return false;
    return `${b.fecha_fin}T${this.normalizarHora(b.hora_fin)}` <= `${b.fecha_inicio}T${this.normalizarHora(b.hora_inicio)}`;
  });

  cambiar(campo: Campo, valor: string): void {
    this.borrador.update(b => ({ ...b, [campo]: valor ?? '' }));
    this.marcar(campo);
    this.mensaje.set('');
  }

  marcar(campo: Campo): void {
    this.tocados.update(campos => campos.includes(campo) ? campos : [...campos, campo]);
  }

  visible(campo: Campo): boolean {
    return this.intentado() || this.tocados().includes(campo);
  }

  enviar(): void {
    this.intentado.set(true);
    const b = this.borrador();
    if (!b.tipo || !b.fecha_inicio || !b.fecha_fin || this.fechasInvertidas() || this.horasIncompletas() || this.finalNoPosterior() || b.motivo.trim().length > 5000) {
      this.mensaje.set('Revise los campos indicados. La solicitud no se ha enviado.');
      return;
    }
    // No se inventan identificadores ni operaciones públicas.
    this.mensaje.set('La solicitud no se ha enviado: no existe un endpoint público de registro ni una consulta pública de las reglas del tipo de ausencia.');
  }

  private normalizarHora(hora: string): string {
    return hora.length === 5 ? `${hora}:00` : hora;
  }
}