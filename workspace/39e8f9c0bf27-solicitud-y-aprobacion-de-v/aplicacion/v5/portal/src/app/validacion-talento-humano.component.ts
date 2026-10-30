import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-validacion-talento-humano',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="card">
      <h2>Validación de Talento Humano</h2>
      <div class="card"><h3>Revisor de Talento Humano</h3><p>Nombre: Andrea Torres</p><p>Área: Talento Humano</p><p>Rol: Validador</p><p>Turno: Mañana</p></div>
      <div class="card"><h3>Solicitud a validar</h3><p>Solicitante: Laura Gómez</p><p>Tipo de ausencia: Vacaciones</p><p>Caso requiere revisión adicional: Sí</p><p>Observación previa: Aprobada por jefe inmediato</p></div>
      <label class="field">Observaciones de Talento Humano<input [(ngModel)]="observaciones" name="observaciones" /></label>
      <div class="actions"><button type="button" (click)="validar()">Validar y aprobar</button><button type="button" class="danger" (click)="rechazar()">Rechazar solicitud</button></div>
      <div class="success" *ngIf="resultado() === 'aprobada'">Solicitud validada y aprobada.</div>
      <div class="alert" *ngIf="resultado() === 'rechazada'">Solicitud rechazada.</div>
    </section>
  `,
})
export class ValidacionTalentoHumanoComponent { observaciones = ''; resultado = signal<'aprobada' | 'rechazada' | ''>(''); validar() { this.resultado.set('aprobada'); } rechazar() { this.resultado.set('rechazada'); } }