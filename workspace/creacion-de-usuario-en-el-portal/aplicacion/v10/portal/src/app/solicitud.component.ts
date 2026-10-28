import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

interface Solicitud {
  cedula: string;
  nombres_completos: string;
  telefono: string;
  correo_electronico: string;
  fecha_nacimiento: string; // YYYY-MM-DD
  nivel_estudios: string;
}

const nivelesValidos = [
  'Bachillerato',
  'Técnico',
  'Tecnológico',
  'Universitario',
  'Posgrado'
];

@Component({
  selector: 'app-solicitud',
  standalone: true,
  imports: [FormsModule],
  template: `
  <main class="card">
    <h1>Solicitud de creación de usuario corporativo</h1>
    <form (ngSubmit)="enviarSolicitud()" #form="ngForm" novalidate>
      <label class="field">Cédula *
        <input name="cedula" [(ngModel)]="solicitudValue.cedula" required #cedula="ngModel" />
      </label>
      <div *ngIf="cedula.invalid && cedula.touched" class="error">Cédula es obligatoria.</div>

      <label class="field">Nombres completos *
        <input name="nombres_completos" [(ngModel)]="solicitudValue.nombres_completos" required #nombres="ngModel" />
      </label>
      <div *ngIf="nombres.invalid && nombres.touched" class="error">Nombres completos son obligatorios.</div>

      <label class="field">Teléfono *
        <input name="telefono" [(ngModel)]="solicitudValue.telefono" required #telefono="ngModel" />
      </label>
      <div *ngIf="telefono.invalid && telefono.touched" class="error">Teléfono es obligatorio.</div>

      <label class="field">Correo electrónico *
        <input name="correo_electronico" type="email" [(ngModel)]="solicitudValue.correo_electronico" required #correo="ngModel" />
      </label>
      <div *ngIf="correo.invalid && correo.touched" class="error">Correo electrónico válido es obligatorio.</div>

      <label class="field">Fecha de nacimiento *
        <input name="fecha_nacimiento" type="date" [(ngModel)]="solicitudValue.fecha_nacimiento" required #fechaNac="ngModel" />
      </label>
      <div *ngIf="fechaNac.invalid && fechaNac.touched" class="error">Fecha de nacimiento es obligatoria.</div>

      <label class="field">Nivel de estudios *
        <select name="nivel_estudios" [(ngModel)]="solicitudValue.nivel_estudios" required #nivelEstudios="ngModel">
          <option value="" disabled>Seleccione nivel</option>
          <option *ngFor="let nivel of niveles" [value]="nivel">{{nivel}}</option>
        </select>
      </label>
      <div *ngIf="nivelEstudios.invalid && nivelEstudios.touched" class="error">Nivel de estudios es obligatorio.</div>

      <div *ngIf="errores.length > 0" class="alert">
        <ul>
          <li *ngFor="let error of errores" class="error">{{error}}</li>
        </ul>
      </div>

      <div *ngIf="exito" class="success">Solicitud enviada con ID: {{resultado?.id}} Estado: {{resultado?.estado}}</div>

      <div class="actions">
        <button type="submit" [disabled]="!form.form.valid || errores.length > 0">Enviar solicitud</button>
      </div>
    </form>
  </main>
  `
})
export class SolicitudComponent {
  niveles = ['Primaria', 'Secundaria', 'Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado'];

  solicitud = signal<Solicitud>({
    cedula: '',
    nombres_completos: '',
    telefono: '',
    correo_electronico: '',
    fecha_nacimiento: '',
    nivel_estudios: ''
  });

  // Para usar en template, extraemos valor actual
  get solicitudValue() {
    return this.solicitud();
  }

  errores = signal<string[]>([]);
  exito = signal(false);
  resultado = signal<{id: number; estado: string} | null>(null);

  private validar(): boolean {
    const errores: string[] = [];
    const s = this.solicitud();

    // Validar campos obligatorios
    if (!s.cedula.trim()) errores.push('Cédula es obligatoria.');
    if (!s.nombres_completos.trim()) errores.push('Nombres completos son obligatorios.');
    if (!s.telefono.trim()) errores.push('Teléfono es obligatorio.');
    if (!s.correo_electronico.trim()) errores.push('Correo electrónico es obligatorio.');
    if (!s.fecha_nacimiento.trim()) errores.push('Fecha de nacimiento es obligatoria.');
    if (!s.nivel_estudios.trim()) errores.push('Nivel de estudios es obligatorio.');

    // Validar nivel de estudios mínimo bachillerato
    const nivelIndex = this.niveles.indexOf(s.nivel_estudios);
    const indiceBachillerato = this.niveles.indexOf('Bachillerato');
    if (nivelIndex < indiceBachillerato) {
      errores.push('Nivel de estudios mínimo: bachillerato');
    }

    // Validar edad > 23 años
    if (s.fecha_nacimiento) {
      const fechaNac = new Date(s.fecha_nacimiento);
      const hoy = new Date();
      let edad = hoy.getFullYear() - fechaNac.getFullYear();
      const m = hoy.getMonth() - fechaNac.getMonth();
      if (m < 0 || (m === 0 && hoy.getDate() < fechaNac.getDate())) {
        edad--;
      }
      if (edad <= 23) {
        errores.push('La edad debe ser mayor a 23 años');
      }
    }

    this.errores.set(errores);
    return errores.length === 0;
  }

  async enviarSolicitud() {
    this.exito.set(false);
    this.resultado.set(null);

    if (!this.validar()) {
      return;
    }

    const s = this.solicitud();

    try {
      const response = await fetch('/api/solicitudes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(s)
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.errores.set([`Error al enviar solicitud: ${errorText}`]);
        return;
      }

      const data = await response.json();
      this.resultado.set(data);
      this.exito.set(true);
      this.errores.set([]);
      // Limpiar formulario
      this.solicitud.set({
        cedula: '',
        nombres_completos: '',
        telefono: '',
        correo_electronico: '',
        fecha_nacimiento: '',
        nivel_estudios: ''
      });
    } catch (error) {
      this.errores.set([`Error de red al enviar solicitud.`]);
    }
  }
}