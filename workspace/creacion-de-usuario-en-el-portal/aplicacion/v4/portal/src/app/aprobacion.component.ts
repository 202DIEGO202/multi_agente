import { Component, signal } from '@angular/core';

@Component({
  selector: 'aprobacion',
  standalone: true,
  template: `
    <h1>Aprobación de solicitud por líder de área</h1>
    <section class="card">
      <h2>Datos del solicitante</h2>
      <ul>
        <li>Nombre: Juan Pérez</li>
        <li>Cédula: 1234567890</li>
        <li>Área: Finanzas</li>
        <li>Cargo: Analista</li>
        <li>Fecha de nacimiento: 15/04/1985</li>
        <li>Edad: 39 años</li>
        <li>Nivel de estudios: Universitario</li>
      </ul>
    </section>
    <section class="card">
      <h2>Datos del líder de área (aprobador)</h2>
      <ul>
        <li>Nombre: Laura Gómez</li>
        <li>Cargo: Líder de área</li>
        <li>Área: Finanzas</li>
        <li>Correo electrónico: laura.gomez@empresa.com</li>
        <li>Fecha y hora de decisión: --/--/---- --:--</li>
      </ul>
    </section>
    <div class="actions">
      <button (click)="aprobar()">Aprobar solicitud</button>
      <button (click)="rechazar()">Rechazar solicitud</button>
    </div>
    <label class="field">Motivo de rechazo (obligatorio si rechaza)
      <input type="text" [value]="motivoRechazo()" (input)="motivoRechazo.set($any($event.target).value.trim())" />
    </label>
    <div *ngIf="mensajeEstado()" class="alert">{{mensajeEstado()}}</div>
  `
})
export class AprobacionComponent {
  motivoRechazo = signal('');
  mensajeEstado = signal('');

  aprobar() {
    this.mensajeEstado.set('Solicitud aprobada. Notificación enviada al administrador de Active Directory.');
  }

  rechazar() {
    if (!this.motivoRechazo().trim()) {
      this.mensajeEstado.set('Motivo de rechazo es obligatorio para rechazar la solicitud.');
      return;
    }
    this.mensajeEstado.set('Solicitud rechazada con motivo: ' + this.motivoRechazo());
  }
}