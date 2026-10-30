import { CommonModule } from '@angular/common';
import { Component, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-solicitudes-ausencia',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="card">
      <h2>Solicitudes de ausencia</h2>
      <div class="card"><h3>Solicitante</h3><p>Nombre: Laura Gómez</p><p>Documento: 1023456789</p><p>Área: Operaciones</p><p>Cargo: Analista</p></div>
      <form (ngSubmit)="enviar()">
        <label class="field">Tipo de ausencia<input [(ngModel)]="tipoAusencia" name="tipoAusencia" /></label>
        <div class="error" *ngIf="errores().tipoAusencia">Seleccione un tipo de ausencia.</div>
        <label class="field">Fecha de inicio<input type="date" [(ngModel)]="fechaInicio" name="fechaInicio" /></label>
        <div class="error" *ngIf="errores().fechaInicio">Ingrese la fecha de inicio.</div>
        <label class="field">Fecha de fin<input type="date" [(ngModel)]="fechaFin" name="fechaFin" /></label>
        <div class="error" *ngIf="errores().fechaFin">Ingrese la fecha de fin.</div>
        <div class="error" *ngIf="errores().rangoFechas">La fecha de fin debe ser igual o posterior a la fecha de inicio.</div>
        <label class="field">Hora de inicio (si aplica)<input type="time" [(ngModel)]="horaInicio" name="horaInicio" /></label>
        <label class="field">Hora de fin (si aplica)<input type="time" [(ngModel)]="horaFin" name="horaFin" /></label>
        <div class="error" *ngIf="errores().rangoHoras">La hora de fin debe ser posterior a la hora de inicio.</div>
        <label class="field">Motivo u observación del permiso (si aplica al tipo seleccionado)<input [(ngModel)]="motivo" name="motivo" /></label>
        <button type="submit">Enviar solicitud</button>
      </form>
      <div class="success" *ngIf="enviado()">Solicitud enviada correctamente.</div>
      <div class="card"><h3>Historial de solicitudes</h3><p>Solicitud: Vacaciones del 12/07 al 19/07</p><p>Estado: En revisión</p><p>Último cambio: Aprobador asignado</p><p>Solicitud: Permiso personal 03/08</p><p>Estado: Aprobado</p></div>
    </section>
  `,
})
export class SolicitudesAusenciaComponent {
  tipoAusencia = '';
  fechaInicio = '';
  fechaFin = '';
  horaInicio = '';
  horaFin = '';
  motivo = '';
  enviado = signal(false);
  errores = computed(() => {
    const e: Record<string, boolean> = {};
    if (!this.tipoAusencia) e['tipoAusencia'] = true;
    if (!this.fechaInicio) e['fechaInicio'] = true;
    if (!this.fechaFin) e['fechaFin'] = true;
    if (this.fechaInicio && this.fechaFin && this.fechaFin < this.fechaInicio) e['rangoFechas'] = true;
    if (this.horaInicio && this.horaFin && this.horaFin <= this.horaInicio) e['rangoHoras'] = true;
    return e;
  });
  enviar() { if (Object.keys(this.errores()).length === 0) this.enviado.set(true); }
}