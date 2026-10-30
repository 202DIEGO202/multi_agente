import { Component, OnInit, inject } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RevisionStore } from './revision-store';

@Component({
  selector: 'app-talento-humano',
  standalone: true,
  imports: [FormsModule, DatePipe],
  providers: [RevisionStore],
  template: `
    <h1>Validación de Talento Humano</h1>
    @if (store.api.autenticado()) {
      <button type="button" (click)="store.api.cerrarSesion()">Cerrar sesión</button>
      @if (store.error()) { <p role="alert">{{ store.error() }}</p> }
      @if (store.mensaje()) { <p role="status">{{ store.mensaje() }}</p> }
      @if (store.ocupado()) { <p role="status">Cargando…</p> }
      @if (store.permitido()) {
        <section class="card">
          <h2>Revisor de Talento Humano</h2>
          <p>Nombre: {{ store.api.identidad()?.nombre }}</p>
          <p>Área: No informada por la API</p>
          <p>Rol: Talento Humano</p>
          <p>Turno: No informado por la API</p>
        </section>
        <section class="card">
          <h2>Solicitudes pendientes</h2>
          <button type="button" (click)="store.recargar()" [disabled]="store.ocupado()">Actualizar</button>
          @for (item of store.pendientes(); track item.aprobacion_id) {
            <article class="card">
              <p>Solicitante: {{ item.solicitante }} | Tipo: {{ item.tipo_ausencia }} | Fechas: {{ item.fecha_inicio | date:'dd/MM/yyyy' }} - {{ item.fecha_fin | date:'dd/MM/yyyy' }}</p>
              <button type="button" (click)="store.abrir(item)" [disabled]="store.ocupado()">Revisar solicitud</button>
            </article>
          } @empty { @if (!store.ocupado()) { <p>No hay solicitudes de Talento Humano en esta página.</p> } }
          <p>La paginación incluye todas las revisiones asignadas; aquí se muestran las de Talento Humano.</p>
          <button type="button" (click)="store.recargar(-50)" [disabled]="store.ocupado() || store.offset() === 0">Anterior</button>
          <button type="button" (click)="store.recargar(50)" [disabled]="store.ocupado() || store.cantidadPagina() < 50">Siguiente</button>
        </section>
        @if (store.seleccion(); as item) {
          @if (store.detalle(); as detalle) {
            <section class="card">
              <h2>Solicitud a validar</h2>
              <p>Solicitante: {{ item.solicitante }}</p>
              <p>Tipo de ausencia: {{ item.tipo_ausencia }}</p>
              <p>Fechas: {{ detalle.fecha_inicio | date:'dd/MM/yyyy' }} - {{ detalle.fecha_fin | date:'dd/MM/yyyy' }}</p>
              @if (detalle.hora_inicio) { <p>Horas: {{ detalle.hora_inicio }} - {{ detalle.hora_fin }}</p> }
              <p>Caso requiere revisión adicional: Sí, asignada a Talento Humano</p>
              <p>Validación requerida: {{ store.revision()?.requiere_validacion ? 'Sí' : 'No' }}</p>
              <p>Observación del empleado: {{ detalle.motivo || 'Sin observación' }}</p>
              <h3>Observación previa</h3>
              @for (observacion of detalle.observaciones; track observacion.id) {
                <p>{{ observacion.accion }} · {{ observacion.creado_en | date:'dd/MM/yyyy HH:mm' }}: {{ observacion.contenido }}</p>
              } @empty { <p>Sin observaciones previas.</p> }
              <label for="observacion-th">Observaciones de Talento Humano</label>
              <textarea id="observacion-th" name="observacionTH" maxlength="5000"
                [ngModel]="store.observacion()" (ngModelChange)="store.observacion.set($event)"
                [disabled]="store.ocupado() || !store.puedeDecidir()"></textarea>
              <p>El motivo es obligatorio para rechazar.</p>
              @if (store.puedeDecidir()) {
                <button type="button" (click)="store.decidir('VALIDAR_APROBAR')" [disabled]="store.ocupado()">Validar y aprobar</button>
                <button type="button" (click)="store.decidir('RECHAZAR')" [disabled]="store.ocupado() || !store.observacion().trim()">Rechazar solicitud</button>
              } @else { <p>Esta revisión ya no está disponible para decidir. Actualiza la bandeja.</p> }
            </section>
          }
        }
      }
    }
  `
})
export class TalentoHumanoComponent implements OnInit {
  readonly store = inject(RevisionStore);
  ngOnInit(): void { void this.store.iniciar('TALENTO_HUMANO'); }
}