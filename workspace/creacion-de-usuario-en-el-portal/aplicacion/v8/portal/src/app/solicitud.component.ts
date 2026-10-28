import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

interface Solicitud {
  cedula: string;
  nombres: string;
  telefono: string;
  correo_electronico: string;
  fecha_nacimiento: string;
  nivel_estudios: string;
}

const nivelesValidos = ['Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado'];
const nivelesPermitidos = ['Primaria', 'Secundaria', 'Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado'];

@Component({
  selector: 'app-solicitud',
  standalone: true,
  imports: [FormsModule],
  template: `
  <main class="card">
    <h1>Solicitud de creación de usuario corporativo</h1>
    <form (ngSubmit)="enviarSolicitud()" #form="ngForm" novalidate>
      <label class="field">Cédula *
        <input name="cedula" [(ngModel)]="solicitud().cedula" required #cedula="ngModel" />
      </label>
      <div *ngIf="cedula.invalid && cedula.touched" class="error">Cédula es obligatoria.</div>

      <label class="field">Nombres completos *
        <input name="nombres" [(ngModel)]="solicitud().nombres" required #nombres="ngModel" />
      </label>
      <div *ngIf="nombres.invalid && nombres.touched" class="error">Nombres completos son obligatorios.</div>

      <label class="field">Teléfono *
        <input name="telefono" [(ngModel)]="solicitud().telefono" required #telefono="ngModel" />
      </label>
      <div *ngIf="telefono.invalid && telefono.touched" class="error">Teléfono es obligatorio.</div>

      <label class="field">Correo electrónico *
        <input name="correo_electronico" type="email" [(ngModel)]="solicitud().correo_electronico" required #correo="ngModel" />
      </label>
      <div *ngIf="correo.invalid && correo.touched" class="error">Correo electrónico válido es obligatorio.</div>

      <label class="field">Fecha de nacimiento *
        <input name="fecha_nacimiento" type="date" [(ngModel)]="solicitud().fecha_nacimiento" required #fechaNac="ngModel" />
      </label>
      <div *ngIf="fechaNac.invalid && fechaNac.touched" class="error">Fecha de nacimiento es obligatoria.</div>

      <label class="field">Nivel de estudios *
        <select name="nivel_estudios" [(ngModel)]="solicitud().nivel_estudios" required #nivelEstudios="ngModel">
          <option value="" disabled>Seleccione nivel</option>
          <option *ngFor="let nivel of nivelesPermitidos" [value]="nivel">{{nivel}}</option>
        </select>
      </label>
      <div *ngIf="nivelEstudios.invalid && nivelEstudios.touched" class="error">Nivel de estudios es obligatorio.</div>

      <div *ngIf="errores.length > 0" class="alert">
        <ul>
          <li *ngFor="let error of errores" class="error">{{error}}</li>
        </ul>
      </div>

      <div class="actions">
        <button type="submit" [disabled]="!form.form.valid || errores.length > 0">Enviar solicitud</button>
      </div>

      <div *ngIf="resultado" class="success">
        Solicitud enviada con ID: <span class="badge">{{resultado.id}}</span>, Estado: <span class="badge">{{resultado.estado}}</span>
      </div>
    </form>
  </main>
  `
})
export class SolicitudComponent {
  nivelesPermitidos = nivelesPermitidos;

  solicitud = signal<Solicitud>({
    cedula: '',
    nombres: '',
    telefono: '',
    correo_electronico: '',
    fecha_nacimiento: '',
    nivel_estudios: ''
  });

  errores = signal<string[]>([]);
  resultado = signal<{id: number; estado: string} | null>(null);

  // Calcula edad en años desde fecha de nacimiento
  private calcularEdad(fecha: string): number {
    if (!fecha) return 0;
    const hoy = new Date();
    const nac = new Date(fecha);
    let edad = hoy.getFullYear() - nac.getFullYear();
    const m = hoy.getMonth() - nac.getMonth();
    if (m < 0 || (m === 0 && hoy.getDate() < nac.getDate())) {
      edad--;
    }
    return edad;
  }

  // Valida reglas de negocio y campos
  private validar(): string[] {
    const errs: string[] = [];
    const s = this.solicitud();

    // Campos obligatorios
    if (!s.cedula.trim()) errs.push('Cédula es obligatoria.');
    if (!s.nombres.trim()) errs.push('Nombres completos son obligatorios.');
    if (!s.telefono.trim()) errs.push('Teléfono es obligatorio.');
    if (!s.correo_electronico.trim()) errs.push('Correo electrónico es obligatorio.');
    if (!s.fecha_nacimiento.trim()) errs.push('Fecha de nacimiento es obligatoria.');
    if (!s.nivel_estudios.trim()) errs.push('Nivel de estudios es obligatorio.');

    // Validar nivel de estudios mínimo bachillerato
    if (s.nivel_estudios && !nivelesValidos.includes(s.nivel_estudios)) {
      errs.push('Nivel de estudios mínimo: bachillerato');
    }

    // Validar edad > 23
    if (s.fecha_nacimiento) {
      const edad = this.calcularEdad(s.fecha_nacimiento);
      if (edad <= 23) {
        errs.push('La edad debe ser mayor a 23 años');
      }
    }

    return errs;
  }

  async enviarSolicitud() {
    this.errores.set(this.validar());
    if (this.errores().length > 0) {
      this.resultado.set(null);
      return;
    }

    const s = this.solicitud();

    try {
      const resp = await fetch('/api/solicitudes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(s)
      });
      if (!resp.ok) {
        const text = await resp.text();
        this.errores.set([`Error al enviar solicitud: ${resp.status} ${text}`]);
        this.resultado.set(null);
        return;
      }
      const data = await resp.json();
      this.resultado.set({ id: data.id, estado: data.estado });
      this.errores.set([]);
      // Limpiar formulario
      this.solicitud.set({ cedula: '', nombres: '', telefono: '', correo_electronico: '', fecha_nacimiento: '', nivel_estudios: '' });
    } catch (e) {
      this.errores.set(['Error de red al enviar solicitud.']);
      this.resultado.set(null);
    }
  }
}