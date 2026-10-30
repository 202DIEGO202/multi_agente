import { Component, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

@Component({
  selector: 'app-detalle-solicitud',
  standalone: true,
  imports: [RouterLink],
  template: `
    <h1>Notificaciones y detalle de solicitud</h1>
    <a routerLink="/">Volver a solicitudes</a>
    @if (errorIdentificador()) {
      <p class="error" role="alert">{{ errorIdentificador() }}</p>
    }
    <p class="alert" role="status">El contrato actual no incluye endpoints públicos para consultar solicitudes, historiales o notificaciones. No se han consultado datos protegidos.</p>
    <section class="card">
      <h2>Detalle e historial</h2>
      <p>No es posible verificar la solicitud ni mostrar su estado o historial mediante la API pública.</p>
    </section>
    <section class="card">
      <h2>Notificación de cambio de estado</h2>
      <p>Las notificaciones no están disponibles mediante la API pública.</p>
    </section>
    <section class="card">
      <h2>Notificación de pendientes de revisión</h2>
      <p>Los avisos de pendientes requieren acceso autorizado. Este portal no consulta información de aprobadores ni permite revisar o aprobar solicitudes.</p>
    </section>
  `
})
export class DetalleSolicitudComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  readonly errorIdentificador = signal('');

  ngOnInit(): void {
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(params => {
      const raw = params.get('id') || '';
      const id = /^\d+$/.test(raw) ? Number(raw) : 0;
      this.errorIdentificador.set(Number.isSafeInteger(id) && id > 0
        ? ''
        : 'El identificador de solicitud debe ser un entero positivo.');
    });
  }
}