import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';

@Component({
  selector: 'app-notificaciones-detalle-solicitud',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="card">
      <h2>Notificaciones y detalle de solicitud</h2>
      <div class="card"><h3>Notificación de cambio de estado</h3><p>Solicitud: Vacaciones del 12/07 al 19/07</p><p>Estado anterior: En revisión</p><p>Nuevo estado: Aprobada</p><p>Fecha del aviso: 19/06/2026</p></div>
      <div class="card"><h3>Notificación de pendientes de revisión</h3><p>Solicitud: Permiso personal 03/08</p><p>Estado: Pendiente de revisión</p><p>Aprobador: Jefe inmediato</p><p>Prioridad: Normal</p></div>
      <div class="card"><h3>Detalle e historial</h3><p>Tipo de ausencia: Vacaciones</p><p>Fechas: 12/07/2026 - 19/07/2026</p><p>Horas: No aplica</p><p>Observación: Viaje familiar</p><p>Historial: Enviada &gt; En revisión &gt; Aprobada</p></div>
      <p class="alert">Pantalla de consulta.</p>
    </section>
  `,
})
export class NotificacionesDetalleSolicitudComponent {}