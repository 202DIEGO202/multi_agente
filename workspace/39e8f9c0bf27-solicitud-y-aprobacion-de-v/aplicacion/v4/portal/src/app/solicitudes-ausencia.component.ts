import { CommonModule } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-solicitudes-ausencia',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="card">
      <h1>Solicitudes de ausencia</h1>

      <div class="card">
        <h2>Solicitante</h2>
        <p>Nombre: Laura Gómez</p>
        <p>Documento: 1023456789</p>
        <p>Área: Operaciones</p>
        <p>Cargo: Analista</p>
      </div>

      <form (submit)="$event.preventDefault(); enviar()">
        <label class="field">Tipo de ausencia
          <select [(ngModel)]="tipoAusencia" name="tipoAusencia" required>
            <option value="">Seleccione</option>
            <option>Vacaciones</option>
            <option>Permiso médico</option>
            <option>Permiso personal</option>
            <option>Otro permiso</option>
          </select>
        </label>
        <label class="field">Fecha de inicio<input [(ngModel)]="fechaInicio" name="fechaInicio" type="date" required></label>
        <label class="field">Fecha de fin<input [(ngModel)]="fechaFin" name="fechaFin" type="date" required></label>
        <label class="field">Hora de inicio (si aplica)<input [(ngModel)]="horaInicio" name="horaInicio" type="time"></label>
        <label class="field">Hora de fin (si aplica)<input [(ngModel)]="horaFin" name="horaFin" type="time"></label>
        <label class="field">Motivo u observación del permiso (si aplica al tipo seleccionado)<input [(ngModel)]="motivo" name="motivo"></label>
        <button type="submit">Enviar solicitud</button>
      </form>

      <p class="success" *ngIf="resultado()">{{ resultado() }}</p>

      <div class="card">
        <h2>Historial de solicitudes</h2>
        <p>Solicitud: Vacaciones del 12/07 al 19/07</p>
        <p>Estado: En revisión</p>
        <p>Último cambio: Aprobador asignado</p>
        <p>Solicitud: Permiso personal 03/08</p>
        <p>Estado: Aprobado</p>
        <a routerLink="/notificaciones-detalle-solicitud">Consultar detalle e historial</a>
      </div>
    </section>
  `,
})
export class solicitudesAusenciaComponent implements OnInit {
  tipoAusencia = '';
  fechaInicio = '';
  fechaFin = '';
  horaInicio = '';
  horaFin = '';
  motivo = '';
  resultado = signal('');
  ngOnInit() {}
  enviar() { this.resultado.set('Solicitud enviada correctamente.'); }
}