import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-notificaciones-detalle',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section>
      <h1>Notificaciones y detalle de solicitud</h1>

      <div class="card">
        <h2>Notificación de cambio de estado</h2>
        <div>Solicitud: Vacaciones del 12/07 al 19/07</div>
        <div>Estado anterior: En revisión</div>
        <div>Nuevo estado: Aprobada</div>
        <div>Fecha del aviso: 19/06/2026</div>
      </div>

      <div class="card">
        <h2>Notificación de pendientes de revisión</h2>
        <div>Solicitud: Permiso personal 03/08</div>
        <div>Estado: Pendiente de revisión</div>
        <div>Aprobador: Jefe inmediato</div>
        <div>Prioridad: Normal</div>
      </div>

      <div class="card">
        <h2>Detalle e historial</h2>
        <div>Tipo de ausencia: Vacaciones</div>
        <div>Fechas: 12/07/2026 - 19/07/2026</div>
        <div>Horas: No aplica</div>
        <div>Observación: Viaje familiar</div>
        <div>Historial: Enviada &gt; En revisión &gt; Aprobada</div>
      </div>

      <a routerLink="/solicitudes">Volver a solicitudes</a>
    </section>
  `,
})
export class NotificacionesDetalleComponent {}