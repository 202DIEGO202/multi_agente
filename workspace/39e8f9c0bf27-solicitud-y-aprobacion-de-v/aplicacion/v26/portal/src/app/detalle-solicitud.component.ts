import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

@Component({
  selector: 'app-detalle-solicitud',
  standalone: true,
  imports: [RouterLink],
  template: `
    <h1>Notificaciones y detalle de solicitud</h1>
    <p class="alert" role="status">{{ aviso() }}</p>
    <section class="card" aria-labelledby="cambio">
      <h2 id="cambio">Notificación de cambio de estado</h2>
      <p>No disponible: no hay una consulta pública de notificaciones del empleado.</p>
    </section>
    <section class="card" aria-labelledby="pendientes">
      <h2 id="pendientes">Notificación de pendientes de revisión</h2>
      <p>Los avisos de revisión corresponden al aprobador autorizado. Este portal no puede consultar su bandeja ni sus notificaciones.</p>
    </section>
    <section class="card" aria-labelledby="detalle">
      <h2 id="detalle">Detalle e historial</h2>
      <p>No se han cargado datos de la solicitud ni su historial. El contrato no proporciona endpoints públicos para realizar estas consultas con autorización y trazabilidad.</p>
    </section>
    <div class="actions">
      <button type="button" class="secondary" routerLink="/">Volver a solicitudes</button>
    </div>
  `
})
export class DetalleSolicitudComponent {
  private readonly route = inject(ActivatedRoute);
  readonly aviso = signal('El detalle no está disponible en el portal con el contrato actual.');

  constructor() {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id || !/^[1-9]\d*$/.test(id)) {
      this.aviso.set('El identificador de solicitud debe ser un entero positivo. No se ha realizado ninguna consulta.');
    }
  }
}