import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-administracion-tipos-ausencia',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="card">
      <h1>Administración de tipos de ausencia</h1>
      <div class="card">
        <h2>Catálogo de tipos de ausencia</h2>
        <p>Tipo: Vacaciones | Estado: Activo | Flujo: Jefe inmediato &gt; Talento Humano</p>
        <p>Tipo: Permiso personal | Estado: Activo | Flujo: Jefe inmediato</p>
        <p>Tipo: Permiso médico | Estado: Activo | Flujo: Talento Humano</p>
      </div>
      <label class="field">Nombre del tipo de ausencia<input [(ngModel)]="nombre" name="nombre" required></label>
      <label class="field">Estado del tipo
        <select [(ngModel)]="estado" name="estado" required>
          <option>Activo</option><option>Inactivo</option>
        </select>
      </label>
      <label class="field">Flujo de aprobación
        <select [(ngModel)]="flujo" name="flujo" required>
          <option>Jefe inmediato</option>
          <option>Jefe inmediato &gt; Talento Humano</option>
          <option>Talento Humano</option>
        </select>
      </label>
      <button type="button">Guardar tipo de ausencia</button>
    </section>
  `,
})
export class administracionTiposAusenciaComponent { nombre = signal(''); estado = signal(''); flujo = signal(''); }