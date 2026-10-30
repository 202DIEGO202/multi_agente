import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-validacion-talento-humano',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="card">
      <h1>Validación de Talento Humano</h1>
      <div class="card">
        <h2>Revisor de Talento Humano</h2>
        <p>Nombre: Andrea Torres</p>
        <p>Área: Talento Humano</p>
        <p>Rol: Validador</p>
        <p>Turno: Mañana</p>
      </div>
      <div class="card">
        <h2>Solicitud a validar</h2>
        <p>Solicitante: Laura Gómez</p>
        <p>Tipo de ausencia: Vacaciones</p>
        <p>Caso requiere revisión adicional: Sí</p>
        <p>Observación previa: Aprobada por jefe inmediato</p>
      </div>
      <label class="field">Observaciones de Talento Humano<input [(ngModel)]="obs" name="obs"></label>
      <button type="button">Validar y aprobar</button>
      <button type="button" class="danger">Rechazar solicitud</button>
    </section>
  `,
})
export class validacionTalentoHumanoComponent { obs = signal(''); }