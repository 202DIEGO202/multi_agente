import { Component, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-pa-001',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="card">
      <h2>Solicitudes de ausencia</h2>

      <div class="card">
        <h3>Solicitante</h3>
        <p>Nombre: Laura Gómez</p>
        <p>Documento: 1023456789</p>
        <p>Área: Operaciones</p>
        <p>Cargo: Analista</p>
      </div>

      <form (ngSubmit)="enviar()">
        <label class="field">Tipo de ausencia *
          <select [(ngModel)]="tipoAusencia" name="tipoAusencia" required>
            <option value="">Seleccione</option>
            <option>Vacaciones</option>
            <option>Permiso médico</option>
            <option>Permiso personal</option>
            <option>Otro permiso</option>
          </select>
        </label>
        @if (errores().tipoAusencia) {<div class="error">{{ errores().tipoAusencia }}</div>}

        <label class="field">Fecha de inicio *
          <input type="date" [(ngModel)]="fechaInicio" name="fechaInicio" required />
        </label>
        @if (errores().fechaInicio) {<div class="error">{{ errores().fechaInicio }}</div>}

        <label class="field">Fecha de fin *
          <input type="date" [(ngModel)]="fechaFin" name="fechaFin" required />
        </label>
        @if (errores().fechaFin) {<div class="error">{{ errores().fechaFin }}</div>}

        <label class="field">Hora de inicio (si aplica)
          <input type="time" [(ngModel)]="horaInicio" name="horaInicio" />
        </label>

        <label class="field">Hora de fin (si aplica)
          <input type="time" [(ngModel)]="horaFin" name="horaFin" />
        </label>

        <label class="field">Motivo u observación del permiso (si aplica al tipo seleccionado)
          <input [(ngModel)]="motivo" name="motivo" />
        </label>

        <button type="submit">Enviar solicitud</button>
      </form>

      <div class="card">
        <h3>Historial de solicitudes</h3>
        <p>Solicitud: Vacaciones del 12/07 al 19/07</p>
        <p>Estado: En revisión</p>
        <p>Último cambio: Aprobador asignado</p>
        <p>Solicitud: Permiso personal 03/08</p>
        <p>Estado: Aprobado</p>
        <button type="button" class="secondary">Consultar detalle e historial</button>
      </div>

      @if (mensaje()) {<div class="success">{{ mensaje() }}</div>}
    </section>
  `,
})
export class Pa001Component {
  tipoAusencia = '';
  fechaInicio = '';
  fechaFin = '';
  horaInicio = '';
  horaFin = '';
  motivo = '';
  mensaje = signal('');
  errores = signal<{ tipoAusencia?: string; fechaInicio?: string; fechaFin?: string }>({});

  enviar() {
    const errores: any = {};
    if (!this.tipoAusencia) errores.tipoAusencia = 'Seleccione un tipo de ausencia.';
    if (!this.fechaInicio) errores.fechaInicio = 'La fecha de inicio es obligatoria.';
    if (!this.fechaFin) errores.fechaFin = 'La fecha de fin es obligatoria.';
    this.errores.set(errores);
    if (Object.keys(errores).length) return;
    this.mensaje.set('Solicitud enviada para revisión y aprobación.');
  }
}