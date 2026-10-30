import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ReviewModel } from './review-model';

@Component({
  selector: 'app-talento-humano', standalone: true, imports: [FormsModule],
  template: `
    @if (api.authenticated()) {
      <section class="page">
        <h1>Validación de Talento Humano</h1>
        <button type="button" (click)="logout()">Cerrar sesión</button>
        <section class="card">
          <h2>Revisor de Talento Humano</h2>
          <p>La identidad y los permisos del revisor se verifican en el servidor mediante la credencial administrativa. La API administrativa no expone una ficha del operador.</p>
        </section>
        @if (error()) { <p role="alert" class="alert">{{ error() }}</p> }
        @if (message()) { <p role="status">{{ message() }}</p> }
        @if (busy()) { <p role="status">Cargando…</p> }
        <section class="card">
          <h2>Solicitudes pendientes</h2>
          <button type="button" (click)="load()" [disabled]="busy()">Actualizar bandeja</button>
          @for (item of items(); track item.id) {
            <article class="card">
              <p>Solicitante: {{ item.solicitante }} | Tipo: {{ item.tipo_ausencia }} | Fechas: {{ item.fecha_inicio }} - {{ item.fecha_fin }}</p>
              <button type="button" (click)="open(item)" [disabled]="busy()">Validar solicitud #{{ item.id }}</button>
            </article>
          } @empty { @if (!busy()) { <p>No hay solicitudes pendientes en esta página.</p> } }
          <button type="button" (click)="load(offset() - 50)" [disabled]="busy() || offset() === 0">Anterior</button>
          <span>Página {{ offset() / 50 + 1 }}</span>
          <button type="button" (click)="load(offset() + 50)" [disabled]="busy() || items().length < 50">Siguiente</button>
        </section>
        @if (selected(); as item) {
          <section class="card">
            <h2>Solicitud a validar</h2>
            <p>Solicitante: {{ item.solicitante.nombre }}</p>
            <p>Área: {{ item.solicitante.area }}</p>
            <p>Tipo de ausencia: {{ selectedSummary()?.tipo_ausencia }}</p>
            <p>Fechas: {{ item.fecha_inicio }} - {{ item.fecha_fin }}</p>
            @if (item.hora_inicio) { <p>Horas: {{ item.hora_inicio }} - {{ item.hora_fin }}</p> }
            <p>Observación del empleado: {{ item.motivo || 'Sin observación' }}</p>
            <p>Caso requiere revisión adicional: {{ canDecide() ? 'Sí' : 'No hay un paso pendiente de Talento Humano' }}</p>
            <p>Estado: {{ item.estado_codigo }} | Versión: {{ item.version }}</p>
            <h3>Revisiones del flujo</h3>
            @for (revision of item.revisiones; track revision.id) { <p>{{ revision.orden }}. {{ revision.rol_codigo }} | {{ revision.estado }}</p> }
            <label for="th-observaciones">Observaciones de Talento Humano</label>
            <textarea id="th-observaciones" name="observaciones" maxlength="4000" [ngModel]="observation()" (ngModelChange)="observation.set($event)" [disabled]="busy() || !canDecide()"></textarea>
            <p>Las observaciones son obligatorias para rechazar. Consulte el historial para ver las observaciones previas.</p>
            @if (canDecide()) {
              <button type="button" (click)="decide('VALIDAR_Y_APROBAR')" [disabled]="busy()">Validar y aprobar</button>
              <button type="button" (click)="decide('RECHAZAR')" [disabled]="busy() || !observation().trim()">Rechazar solicitud</button>
            } @else { <p>La validación solo está disponible cuando el paso pendiente corresponde a Talento Humano.</p> }
            <button type="button" (click)="showHistory()" [disabled]="busy()">Consultar historial</button>
            @if (history(); as h) {
              <h3>Historial</h3>
              @for (event of h.historial; track event.id) { <p>{{ event.creado_en }} | Versión {{ event.version }} | {{ event.estado_anterior }} → {{ event.estado_nuevo }}</p> } @empty { <p>Sin eventos.</p> }
              <h3>Decisiones</h3>
              @for (event of h.decisiones; track event.id) { <p>{{ event.creado_en }} | Actor {{ event.actor_id }} | {{ event.accion }}</p> } @empty { <p>Sin decisiones.</p> }
              <h3>Observación previa</h3>
              @for (event of h.observaciones; track event.id) { <p>{{ event.creado_en }} | Actor {{ event.actor_id }} | {{ event.texto }}</p> } @empty { <p>Sin observaciones previas.</p> }
            }
          </section>
        }
        <section class="card">
          <h2>Notificaciones de revisión</h2>
          @if (noticeError()) { <p role="alert">{{ noticeError() }}</p> }
          <button type="button" (click)="loadNotices()">Actualizar avisos</button>
          @for (notice of notices(); track notice.id) { <p>Solicitud #{{ notice.solicitud_id }} pendiente de revisión | {{ notice.creado_en }} | Prioridad: {{ notice.prioridad }}</p> } @empty { <p>No hay avisos en esta página.</p> }
          <button type="button" (click)="loadNotices(noticeOffset() - 50)" [disabled]="noticeOffset() === 0">Avisos anteriores</button>
          <button type="button" (click)="loadNotices(noticeOffset() + 50)" [disabled]="notices().length < 50">Avisos siguientes</button>
        </section>
      </section>
    }
  `
})
export class TalentoHumanoComponent extends ReviewModel {
  constructor() { super('TALENTO_HUMANO'); }
}