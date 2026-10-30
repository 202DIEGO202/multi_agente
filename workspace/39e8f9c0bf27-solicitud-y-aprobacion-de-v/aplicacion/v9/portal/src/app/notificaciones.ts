import { Component, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-notificaciones',
  standalone: true,
  imports: [RouterLink],
  template: `
    <h1>Notificaciones y detalle de solicitud</h1>
    <p class="alert" role="status">{{ aviso() }}</p>
    <section class="card">
      <h2>Notificación de cambio de estado</h2>
      <p>No hay avisos consultables mediante la API pública disponible.</p>
    </section>
    <section class="card">
      <h2>Notificación de pendientes de revisión</h2>
      <p>Las notificaciones de aprobadores no se consultan desde este portal.</p>
    </section>
    <section class="card">
      <h2>Detalle e historial</h2>
      <p>No hay una solicitud disponible para consultar. No se muestran datos de ejemplo como si fueran datos reales.</p>
    </section>
    <a routerLink="/">Volver a solicitudes</a>
  `
})
export class NotificacionesComponent {
  readonly aviso = signal('El contrato recibido no incluye endpoints públicos para notificaciones, detalle o historial del solicitante.');
}