import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-pa-004',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="card">
      <h2>Validación de Talento Humano</h2>

      <div class="card">
        <h3>Revisor de Talento Humano</h3>
        <p>Nombre: Andrea Torres</p>
        <p>Área: Talento Humano</p>
        <p>Rol: Validador</p>
        <p>Turno: Mañana</p>
      </div>

      <div class="card">
        <h3>Solicitud a validar</h3>
        <p>Solicitante: Laura Gómez</p>
        <p>Tipo de ausencia: Vacaciones</p>
        <p>Caso requiere revisión adicional: Sí</p>
        <p>Observación previa: Aprobada por jefe inmediato</p>
      </div>

      <label class="field">Observaciones de Talento Humano
        <input [(ngModel)]="observaciones" name="observaciones" />
      </label>

      <div class="actions">
        <button type="button" (click)="aprobar()">Validar y aprobar</button>
        <button type="button" class="danger" (click)="rechazar()">Rechazar solicitud</button>
      </div>

      @if (mensaje()) {<div class="success">{{ mensaje() }}</div>}
    </section>
  `,
})
export class Pa004Component {
  observaciones = '';
  mensaje = signal('');

  aprobar() {
    this.mensaje.set('Solicitud validada y aprobada con observaciones registradas.');
  }

  rechazar() {
    this.mensaje.set('Solicitud rechazada con observaciones registradas.');
  }
}