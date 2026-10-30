import { Component, DestroyRef, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

// PA-002: seguimiento del empleado, sin bandeja de aprobadores.
@Component({
  selector: 'app-notificaciones',
  standalone: true,
  imports: [RouterLink],
  template: `
    <section>
      <h1>Notificaciones y detalle de solicitud</h1>
      <p class="alert" role="status">Las consultas no están disponibles: el contrato recibido no ofrece endpoints públicos para notificaciones, detalle o historial.</p>
      <section class="card">
        <h2>Notificación de cambio de estado</h2>
        <p>No se han consultado notificaciones. Esta pantalla no muestra avisos destinados a aprobadores.</p>
      </section>
      <section class="card">
        <h2>Detalle e historial</h2>
        @if (errorDetalle()) {
          <p class="error" role="alert">{{ errorDetalle() }}</p>
        } @else if (solicitudId(); as id) {
          <p>Solicitud seleccionada: {{ id }}</p>
          <p>No se ha consultado su detalle ni su historial. El identificador del enlace no acredita acceso a la solicitud.</p>
        } @else {
          <p>Seleccione una solicitud desde su historial o una notificación cuando las consultas estén disponibles.</p>
        }
      </section>
      <a routerLink="/">Volver a solicitudes</a>
    </section>
  `
})
export class NotificacionesComponent {
  private readonly route = inject(ActivatedRoute);
  readonly solicitudId = signal<number | null>(null);
  readonly errorDetalle = signal('');

  constructor() {
    const subscription = this.route.queryParamMap.subscribe(params => {
      const raw = params.get('solicitud_id');
      const id = raw === null ? null : Number(raw);
      this.errorDetalle.set('');
      if (id !== null && (!Number.isSafeInteger(id) || id < 1)) {
        this.solicitudId.set(null);
        this.errorDetalle.set('El enlace de la solicitud no es válido.');
        return;
      }
      this.solicitudId.set(id);
    });
    inject(DestroyRef).onDestroy(() => subscription.unsubscribe());
  }
}