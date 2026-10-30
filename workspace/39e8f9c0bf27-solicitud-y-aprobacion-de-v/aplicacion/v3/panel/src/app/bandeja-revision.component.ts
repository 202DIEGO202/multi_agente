import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AdminApiService } from './shared/admin-api.service';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="p-4">
      <h1>Bandeja de revisión - Jefe inmediato</h1>
      <p>Solicitudes pendientes</p>

      <button type="button" (click)="cargar()">Actualizar</button>

      <div *ngIf="error()" class="text-red-600">{{ error() }}</div>
      <div *ngIf="api.authError()" class="text-red-600">{{ api.authError() }}</div>

      <ul *ngIf="pendientes().length">
        <li *ngFor="let item of pendientes()" (click)="seleccionar(item)">
          {{ item.resumen }}
        </li>
      </ul>

      <article *ngIf="seleccionada() as s">
        <h2>Solicitud en revisión</h2>
        <p>Solicitante: {{ s.solicitante }}</p>
        <p>Área: {{ s.area }}</p>
        <p>Tipo de ausencia: {{ s.tipoAusencia }}</p>
        <p>Fechas: {{ s.fechas }}</p>
        <p>Observación del empleado: {{ s.observacionEmpleado }}</p>

        <label>
          <span>Observaciones de revisión del jefe</span>
          <textarea [(ngModel)]="observacion"></textarea>
        </label>

        <button type="button" (click)="aprobar(s.id, s.version)">Aprobar solicitud</button>
        <button type="button" (click)="rechazar(s.id, s.version)">Rechazar solicitud</button>
      </article>
    </section>
  `,
})
export class bandejaRevisionComponent {
  readonly api = inject(AdminApiService);
  readonly pendientes = signal<any[]>([]);
  readonly seleccionada = signal<any | null>(null);
  readonly observacion = signal('');
  readonly error = signal('');

  cargar() {
    this.api.get<any[]>('/revisiones/pendientes').subscribe({ next: (data) => this.pendientes.set(data ?? []), error: () => this.error.set('No fue posible cargar la bandeja.') });
  }

  seleccionar(item: any) { this.seleccionada.set(item); }
  aprobar(id: number, version: number) { this.api.post(`/solicitudes/${id}/aprobar`, { version, observacion: this.observacion() }).subscribe(); }
  rechazar(id: number, version: number) { this.api.post(`/solicitudes/${id}/rechazar`, { version, observacion: this.observacion() }).subscribe(); }
}