import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-administracion-tipos-ausencia',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="card">
      <h2>Administración de tipos de ausencia</h2>
      <div class="card"><h3>Catálogo de tipos de ausencia</h3><p>Tipo: Vacaciones | Estado: Activo | Flujo: Jefe inmediato &gt; Talento Humano</p><p>Tipo: Permiso personal | Estado: Activo | Flujo: Jefe inmediato</p><p>Tipo: Permiso médico | Estado: Activo | Flujo: Talento Humano</p></div>
      <form (ngSubmit)="guardar()">
        <label class="field">Nombre del tipo de ausencia<input [(ngModel)]="nombre" name="nombre" /></label>
        <div class="error" *ngIf="errores().nombre">Ingrese el nombre del tipo de ausencia.</div>
        <label class="field">Estado del tipo<select [(ngModel)]="estado" name="estado"><option value="">Seleccione</option><option>Activo</option><option>Inactivo</option></select></label>
        <div class="error" *ngIf="errores().estado">Seleccione el estado del tipo.</div>
        <label class="field">Flujo de aprobación<select [(ngModel)]="flujo" name="flujo"><option value="">Seleccione</option><option>Jefe inmediato</option><option>Jefe inmediato &gt; Talento Humano</option><option>Talento Humano</option></select></label>
        <div class="error" *ngIf="errores().flujo">Seleccione el flujo de aprobación.</div>
        <button type="submit">Guardar tipo de ausencia</button>
      </form>
      <div class="success" *ngIf="guardado()">Tipo de ausencia guardado.</div>
    </section>
  `,
})
export class AdministracionTiposAusenciaComponent { nombre = ''; estado = ''; flujo = ''; guardado = signal(false); errores = signal<Record<string, boolean>>({}); guardar() { const e: Record<string, boolean> = {}; if (!this.nombre) e['nombre'] = true; if (!this.estado) e['estado'] = true; if (!this.flujo) e['flujo'] = true; this.errores.set(e); this.guardado.set(Object.keys(e).length === 0); } }