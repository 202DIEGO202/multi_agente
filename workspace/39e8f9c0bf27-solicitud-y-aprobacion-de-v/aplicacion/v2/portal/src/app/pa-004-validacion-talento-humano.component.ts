import { Component } from '@angular/core';

@Component({
  selector: 'app-pa-004-validacion-talento-humano',
  standalone: true,
  template: `
    <section>
      <h1>Validación de Talento Humano</h1>
      <div>
        <h2>Revisor de Talento Humano</h2>
        <p>Nombre: Andrea Torres</p>
        <p>Área: Talento Humano</p>
        <p>Rol: Validador</p>
        <p>Turno: Mañana</p>
      </div>
      <div>
        <h2>Solicitud a validar</h2>
        <p>Solicitante: Laura Gómez</p>
        <p>Tipo de ausencia: Vacaciones</p>
        <p>Caso requiere revisión adicional: Sí</p>
        <p>Observación previa: Aprobada por jefe inmediato</p>
      </div>
      <label for="obs">Observaciones de Talento Humano</label>
      <textarea id="obs"></textarea>
      <button>Validar y aprobar</button>
      <button>Rechazar solicitud</button>
    </section>
  `
})
export class Pa004ValidacionTalentoHumanoComponent {}