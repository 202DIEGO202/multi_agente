import { Component, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

// PA-001: formulario del empleado, sin funciones de administración.
@Component({
  selector: 'app-solicitudes',
  standalone: true,
  imports: [FormsModule, RouterLink],
  template: `
    <section>
      <h1>Solicitudes de ausencia</h1>
      <p class="alert" role="status">El registro y la consulta de solicitudes no están disponibles: el contrato recibido no ofrece endpoints públicos para estas operaciones.</p>
      <section class="card" aria-label="Registro de solicitud del empleado">
        <h2>Registrar solicitud</h2>
        <p>Los campos marcados con * son obligatorios.</p>
        <form (ngSubmit)="enviarSolicitud()" novalidate>
          <label class="field">Tipo de ausencia <span aria-hidden="true">*</span>
            <select name="tipo" required disabled>
              <option value="">Tipos de ausencia no disponibles</option>
            </select>
          </label>
          <p>No es posible resolver los tipos de ausencia ni sus reglas sin un endpoint público autorizado para el formulario.</p>
          <label class="field">Fecha de inicio <span aria-hidden="true">*</span>
            <input name="fechaInicio" type="date" required [ngModel]="fechaInicio()" (ngModelChange)="fechaInicio.set($event)">
          </label>
          <label class="field">Fecha de fin <span aria-hidden="true">*</span>
            <input name="fechaFin" type="date" required [min]="fechaInicio()" [ngModel]="fechaFin()" (ngModelChange)="fechaFin.set($event)">
          </label>
          <label class="field">Hora de inicio (si aplica)
            <input name="horaInicio" type="time" [ngModel]="horaInicio()" (ngModelChange)="horaInicio.set($event)">
          </label>
          <label class="field">Hora de fin (si aplica)
            <input name="horaFin" type="time" [ngModel]="horaFin()" (ngModelChange)="horaFin.set($event)">
          </label>
          <label class="field">Motivo u observación del permiso (si aplica al tipo seleccionado)
            <input name="motivo" type="text" maxlength="5000" [ngModel]="motivo()" (ngModelChange)="motivo.set($event)">
          </label>
          @if (errorPeriodo()) { <p class="error" role="alert">{{ errorPeriodo() }}</p> }
          @if (error()) { <p class="error" role="alert">{{ error() }}</p> }
          <button type="submit" disabled>Enviar solicitud</button>
        </form>
      </section>
      <section class="card">
        <h2>Historial de solicitudes</h2>
        <p>La consulta del estado y del historial requiere un endpoint público autorizado. No se han consultado ni mostrado datos de solicitudes.</p>
        <a routerLink="/notificaciones">Consultar detalle e historial</a>
      </section>
    </section>
  `
})
export class SolicitudesComponent {
  readonly fechaInicio = signal('');
  readonly fechaFin = signal('');
  readonly horaInicio = signal('');
  readonly horaFin = signal('');
  readonly motivo = signal('');
  readonly error = signal('');

  readonly errorPeriodo = computed(() => {
    const inicio = this.fechaInicio();
    const fin = this.fechaFin();
    if (inicio && fin && fin < inicio) return 'La fecha de fin no puede preceder a la fecha de inicio';
    const horaInicio = this.horaInicio();
    const horaFin = this.horaFin();
    if (!!horaInicio !== !!horaFin) return 'Debe proporcionar ambas horas o ninguna';
    if (inicio && fin && horaInicio && horaFin && `${fin}T${horaFin}` <= `${inicio}T${horaInicio}`) {
      return 'La fecha y hora final deben ser posteriores al inicio';
    }
    return '';
  });

  enviarSolicitud(): void {
    // No se simula una creación ni se invoca una operación protegida.
    this.error.set('El envío no está disponible: no existe un endpoint público autorizado en el contrato recibido.');
  }
}