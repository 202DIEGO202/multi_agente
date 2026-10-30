import { Component, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

interface Formulario {
  tipo: string;
  inicio: string;
  fin: string;
  horaInicio: string;
  horaFin: string;
  motivo: string;
}

@Component({
  selector: 'app-solicitudes',
  standalone: true,
  imports: [FormsModule],
  template: `
    <h1>Solicitudes de ausencia</h1>
    <section class="card" aria-labelledby="solicitante">
      <h2 id="solicitante">Solicitante</h2>
      <p>Los datos del solicitante no están disponibles mediante la API pública.</p>
    </section>
    <p class="alert" role="status">El contrato actual no ofrece acceso público al catálogo, al registro ni a la consulta de solicitudes. Puede completar un borrador en esta pantalla, pero no se enviará ni se guardará.</p>
    <form class="card" (ngSubmit)="enviar()" novalidate>
      <p>Los campos marcados con * son obligatorios.</p>
      <label class="field">Tipo de ausencia <span aria-hidden="true">*</span>
        <select name="tipo" required [ngModel]="formulario().tipo" (ngModelChange)="cambiar('tipo', $event)">
          <option value="">Seleccione un tipo de ausencia</option>
          @for (tipo of opciones; track tipo) {
            <option [value]="tipo">{{ tipo }}</option>
          }
        </select>
      </label>
      <p>Las opciones corresponden al formulario de referencia. Su disponibilidad y las reglas de motivo y horas requieren un catálogo autorizado, que no está disponible en este portal.</p>
      <label class="field">Fecha de inicio <span aria-hidden="true">*</span>
        <input name="inicio" type="date" required [ngModel]="formulario().inicio" (ngModelChange)="cambiar('inicio', $event)">
      </label>
      <label class="field">Fecha de fin <span aria-hidden="true">*</span>
        <input name="fin" type="date" required [min]="formulario().inicio" [ngModel]="formulario().fin" (ngModelChange)="cambiar('fin', $event)">
      </label>
      <label class="field">Hora de inicio (si aplica)
        <input name="horaInicio" type="time" step="1" [ngModel]="formulario().horaInicio" (ngModelChange)="cambiar('horaInicio', $event)">
      </label>
      <label class="field">Hora de fin (si aplica)
        <input name="horaFin" type="time" step="1" [ngModel]="formulario().horaFin" (ngModelChange)="cambiar('horaFin', $event)">
      </label>
      <label class="field">Motivo u observación del permiso (si aplica al tipo seleccionado)
        <input name="motivo" type="text" maxlength="4000" [ngModel]="formulario().motivo" (ngModelChange)="cambiar('motivo', $event)">
      </label>
      @if (editado()) {
        @for (error of errores(); track error) {
          <p class="error" role="alert">{{ error }}</p>
        }
      }
      @if (errorEnvio()) {
        <p class="error" role="alert">{{ errorEnvio() }}</p>
      }
      <button type="submit">Enviar solicitud</button>
    </form>
    <section class="card">
      <h2>Historial de solicitudes</h2>
      <p>No es posible consultar el estado ni el historial: el contrato no incluye endpoints públicos para estas operaciones.</p>
      <button type="button" class="secondary" disabled>Consultar detalle e historial</button>
    </section>
  `
})
export class SolicitudesComponent {
  readonly opciones = ['Vacaciones', 'Permiso médico', 'Permiso personal', 'Otro permiso'];
  readonly formulario = signal<Formulario>({
    tipo: '', inicio: '', fin: '', horaInicio: '', horaFin: '', motivo: ''
  });
  readonly editado = signal(false);
  readonly errorEnvio = signal('');
  readonly errores = computed(() => {
    const form = this.formulario();
    const errors: string[] = [];
    if (!this.opciones.includes(form.tipo)) errors.push('Seleccione un tipo de ausencia activo');
    if (!form.inicio) errors.push('Fecha de inicio es obligatoria');
    if (!form.fin) errors.push('Fecha de fin es obligatoria');
    if (form.inicio && form.fin && form.fin < form.inicio) {
      errors.push('La fecha final debe ser igual o posterior a la inicial');
    }
    if (Boolean(form.horaInicio) !== Boolean(form.horaFin)) {
      errors.push('Debe proporcionar ambas horas');
    }
    if (form.inicio && form.fin && form.horaInicio && form.horaFin) {
      // Comparar horas locales sin conversiones de zona horaria.
      const inicio = `${form.inicio}T${this.normalizarHora(form.horaInicio)}`;
      const fin = `${form.fin}T${this.normalizarHora(form.horaFin)}`;
      if (fin <= inicio) errors.push('El instante final debe ser posterior al inicial');
    }
    if (form.motivo.length > 0 && !form.motivo.trim()) {
      errors.push('No se admiten textos vacíos');
    }
    if (form.motivo.trim().length > 4000) {
      errors.push('El motivo debe tener como máximo 4000 caracteres');
    }
    return errors;
  });

  cambiar(campo: keyof Formulario, valor: string): void {
    this.formulario.update(form => ({ ...form, [campo]: valor }));
    this.editado.set(true);
    this.errorEnvio.set('');
  }

  private normalizarHora(hora: string): string {
    return hora.length === 5 ? `${hora}:00` : hora;
  }

  enviar(): void {
    this.editado.set(true);
    if (this.errores().length) return;
    this.errorEnvio.set('Solicitud no enviada. El contrato actual no dispone de un endpoint público para registrar solicitudes ni permite verificar las reglas del tipo seleccionado.');
  }
}