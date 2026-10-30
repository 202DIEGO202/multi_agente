import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-solicitudes',
  standalone: true,
  imports: [FormsModule, RouterLink],
  template: `
    <h1>Solicitudes de ausencia</h1>
    <section class="card">
      <h2>Solicitante</h2>
      <p>No hay información del solicitante disponible mediante la API pública.</p>
    </section>
    <p class="alert">El contrato disponible no ofrece un servicio público para registrar solicitudes. Los datos de este formulario no se enviarán ni se guardarán.</p>
    <form (ngSubmit)="enviar()" novalidate>
      <label class="field">Tipo de ausencia <span aria-hidden="true">*</span>
        <select name="tipo" required [ngModel]="tipo()" (ngModelChange)="tipo.set($event)">
          <option value="">Seleccione un tipo</option>
          <option value="Vacaciones">Vacaciones</option>
          <option value="Permiso médico">Permiso médico</option>
          <option value="Permiso personal">Permiso personal</option>
          <option value="Otro permiso">Otro permiso</option>
        </select>
      </label>
      <label class="field">Fecha de inicio <span aria-hidden="true">*</span><input name="inicio" type="date" required [ngModel]="inicio()" (ngModelChange)="inicio.set($event)"></label>
      <label class="field">Fecha de fin <span aria-hidden="true">*</span><input name="fin" type="date" required [ngModel]="fin()" (ngModelChange)="fin.set($event)"></label>
      <label class="field">Hora de inicio (si aplica)<input name="horaInicio" type="time" [ngModel]="horaInicio()" (ngModelChange)="horaInicio.set($event)"></label>
      <label class="field">Hora de fin (si aplica)<input name="horaFin" type="time" [ngModel]="horaFin()" (ngModelChange)="horaFin.set($event)"></label>
      <label class="field">Motivo u observación del permiso (si aplica al tipo seleccionado)<input name="motivo" type="text" [ngModel]="motivo()" (ngModelChange)="motivo.set($event)"></label>
      <p>Los campos marcados con * son obligatorios. El servicio público disponible no permite verificar si la solicitud requiere motivo o admite horas.</p>
      @if (errores().length) {
        <div class="error" role="alert">
          @for (error of errores(); track error) { <p>{{ error }}</p> }
        </div>
      }
      @if (aviso()) { <p class="alert" role="status">{{ aviso() }}</p> }
      <button type="submit">Enviar solicitud</button>
    </form>
    <section class="card">
      <h2>Historial de solicitudes</h2>
      <p>No se puede consultar el historial: no existe un endpoint público autorizado en el contrato recibido.</p>
      <a routerLink="/notificaciones">Consultar detalle e historial</a>
    </section>
  `
})
export class SolicitudesComponent {
  readonly tipo = signal('');
  readonly inicio = signal('');
  readonly fin = signal('');
  readonly horaInicio = signal('');
  readonly horaFin = signal('');
  readonly motivo = signal('');
  readonly errores = signal<string[]>([]);
  readonly aviso = signal('');

  enviar(): void {
    const errores: string[] = [];
    if (!this.tipo()) errores.push('Seleccione el tipo de ausencia.');
    if (!this.inicio()) errores.push('La fecha de inicio es obligatoria.');
    if (!this.fin()) errores.push('La fecha de fin es obligatoria.');
    this.errores.set(errores);
    this.aviso.set(errores.length ? '' : 'Solicitud no enviada: el backend no dispone de un endpoint público de registro ni de un modelo de entrada para solicitudes.');
  }
}