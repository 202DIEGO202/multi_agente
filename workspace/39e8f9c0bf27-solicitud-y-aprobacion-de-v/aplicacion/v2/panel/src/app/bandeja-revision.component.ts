import { Component } from '@angular/core';

@Component({
  selector: 'app-bandeja-revision',
  standalone: true,
  template: `
    <section>
      <h1>Bandeja de revisión - Jefe inmediato</h1>
      <p>Solicitudes pendientes</p>
      <p>Solicitud en revisión</p>
      <label>Observaciones de revisión del jefe</label>
      <button>Aprobar solicitud</button>
      <button>Rechazar solicitud</button>
    </section>
  `
})
export class BandejaRevisionComponent {}