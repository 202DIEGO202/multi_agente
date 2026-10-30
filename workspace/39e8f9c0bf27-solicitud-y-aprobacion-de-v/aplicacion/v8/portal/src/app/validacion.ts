import { Component, signal } from '@angular/core';

@Component({
  selector: 'app-validacion',
  standalone: true,
  template: `
    <h1>Validación de Talento Humano</h1>
    <p class="alert" role="status">{{ aviso() }}</p>
    <section class="card">
      <h2>Revisor de Talento Humano</h2>
      <p>No hay una identidad de revisor disponible para este portal público.</p>
    </section>
    <section class="card">
      <h2>Solicitud a validar</h2>
      <p>No hay una solicitud autorizada disponible para validación.</p>
    </section>
    <form>
      <label class="field">Observaciones de Talento Humano<input type="text" disabled></label>
      <div class="actions">
        <button type="button" disabled>Validar y aprobar</button>
        <button type="button" class="danger" disabled>Rechazar solicitud</button>
      </div>
    </form>
  `
})
export class ValidacionComponent {
  readonly aviso = signal('Esta pantalla está asignada al portal en las historias, pero su API requiere acceso administrativo. Las acciones permanecen deshabilitadas: el portal no accede a servicios administrativos.');
}