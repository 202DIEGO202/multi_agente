import { Component, signal } from '@angular/core';

@Component({
  selector: 'app-tipos-ausencia',
  standalone: true,
  template: `
    <h1>Administración de tipos de ausencia</h1>
    <p class="alert" role="status">{{ aviso() }}</p>
    <section class="card">
      <h2>Catálogo de tipos de ausencia</h2>
      <p>El catálogo interno no se expone ni se consulta desde este portal.</p>
    </section>
    <form>
      <label class="field">Nombre del tipo de ausencia <span aria-hidden="true">*</span><input type="text" required disabled></label>
      <label class="field">Estado del tipo <span aria-hidden="true">*</span>
        <select required disabled><option>Activo</option><option>Inactivo</option></select>
      </label>
      <label class="field">Flujo de aprobación <span aria-hidden="true">*</span>
        <select required disabled>
          <option>Jefe inmediato</option>
          <option>Jefe inmediato &gt; Talento Humano</option>
          <option>Talento Humano</option>
        </select>
      </label>
      <button type="button" disabled>Guardar tipo de ausencia</button>
    </form>
  `
})
export class TiposAusenciaComponent {
  readonly aviso = signal('Esta pantalla está asignada al portal en las historias, pero el contrato solo permite administrar el catálogo mediante acceso administrativo. No se realizan consultas ni modificaciones desde el portal.');
}