import { Component, signal } from '@angular/core';

// Validación de email simple
function validarEmail(email: string): boolean {
  const re = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  return re.test(email);
}

// Cálculo de edad a partir de fecha de nacimiento
function calcularEdad(fechaNacimiento: string): number {
  const hoy = new Date();
  const nacimiento = new Date(fechaNacimiento);
  let edad = hoy.getFullYear() - nacimiento.getFullYear();
  const m = hoy.getMonth() - nacimiento.getMonth();
  if (m < 0 || (m === 0 && hoy.getDate() < nacimiento.getDate())) {
    edad--;
  }
  return edad;
}

@Component({
  selector: 'solicitud-form',
  standalone: true,
  template: `
    <h1>Solicitud de creación de usuario corporativo</h1>
    <form (submit)="enviarSolicitud($event)" novalidate>
      <label class="field">Cédula
        <input type="text" [value]="cedula()" (input)="cedula.set($any($event.target).value)" required />
      </label>
      <div *ngIf="errores().cedula" class="error">{{errores().cedula}}</div>

      <label class="field">Nombres completos
        <input type="text" [value]="nombres()" (input)="nombres.set($any($event.target).value)" required />
      </label>
      <div *ngIf="errores().nombres" class="error">{{errores().nombres}}</div>

      <label class="field">Teléfono
        <input type="text" [value]="telefono()" (input)="telefono.set($any($event.target).value)" required />
      </label>
      <div *ngIf="errores().telefono" class="error">{{errores().telefono}}</div>

      <label class="field">Correo electrónico
        <input type="email" [value]="correoElectronico()" (input)="correoElectronico.set($any($event.target).value)" required />
      </label>
      <div *ngIf="errores().correoElectronico" class="error">{{errores().correoElectronico}}</div>

      <label class="field">Fecha de nacimiento
        <input type="date" [value]="fechaNacimiento()" (input)="fechaNacimiento.set($any($event.target).value)" required />
      </label>
      <div *ngIf="errores().fechaNacimiento" class="error">{{errores().fechaNacimiento}}</div>

      <label class="field">Nivel de estudios
        <select [value]="nivelEstudios()" (change)="nivelEstudios.set($any($event.target).value)" required>
          <option value="">Seleccione</option>
          <option *ngFor="let nivel of niveles" [value]="nivel">{{nivel}}</option>
        </select>
      </label>
      <div *ngIf="errores().nivelEstudios" class="error">{{errores().nivelEstudios}}</div>

      <div *ngIf="mensajeError()" class="alert">{{mensajeError()}}</div>

      <div class="actions">
        <button type="submit" [disabled]="enviando()">Enviar solicitud</button>
      </div>
    </form>

    <div *ngIf="confirmacion()" class="success">
      Solicitud enviada con ID: {{confirmacion().id}} - Estado: {{confirmacion().estado}}
    </div>
  `,
  imports: []
})
export class SolicitudFormComponent {
  cedula = signal('');
  nombres = signal('');
  telefono = signal('');
  correoElectronico = signal('');
  fechaNacimiento = signal('');
  nivelEstudios = signal('');

  niveles = ['Primaria', 'Secundaria', 'Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado'];

  errores = signal<{[key:string]: string}>({});
  mensajeError = signal('');
  enviando = signal(false);
  confirmacion = signal<{id:number, estado:string} | null>(null);

  validar(): boolean {
    const errs: {[key:string]: string} = {};
    this.mensajeError.set('');

    if (!this.cedula().trim()) {
      errs.cedula = 'Cédula es obligatoria';
    }
    if (!this.nombres().trim()) {
      errs.nombres = 'Nombres completos son obligatorios';
    }
    if (!this.telefono().trim()) {
      errs.telefono = 'Teléfono es obligatorio';
    }
    if (!this.correoElectronico().trim()) {
      errs.correoElectronico = 'Correo electrónico es obligatorio';
    } else if (!validarEmail(this.correoElectronico().trim())) {
      errs.correoElectronico = 'Correo electrónico no es válido';
    }
    if (!this.fechaNacimiento()) {
      errs.fechaNacimiento = 'Fecha de nacimiento es obligatoria';
    } else {
      const edad = calcularEdad(this.fechaNacimiento());
      if (edad <= 23) {
        errs.fechaNacimiento = 'La edad debe ser mayor a 23 años';
      }
    }
    if (!this.nivelEstudios()) {
      errs.nivelEstudios = 'Nivel de estudios es obligatorio';
    } else {
      // Validar nivel mínimo bachillerato
      const nivel = this.nivelEstudios();
      const indice = this.niveles.indexOf(nivel);
      const indiceMin = this.niveles.indexOf('Bachillerato');
      if (indice < indiceMin) {
        errs.nivelEstudios = 'Nivel de estudios mínimo: bachillerato';
      }
    }

    this.errores.set(errs);
    return Object.keys(errs).length === 0;
  }

  async enviarSolicitud(event: Event) {
    event.preventDefault();
    this.confirmacion.set(null);
    if (!this.validar()) {
      this.mensajeError.set('Corrija los errores antes de enviar la solicitud.');
      return;
    }
    this.enviando.set(true);
    this.mensajeError.set('');

    try {
      const body = {
        cedula: this.cedula().trim(),
        nombres: this.nombres().trim(),
        telefono: this.telefono().trim(),
        correo_electronico: this.correoElectronico().trim(),
        fecha_nacimiento: this.fechaNacimiento(),
        nivel_estudios: this.nivelEstudios()
      };

      const resp = await fetch('/api/solicitudes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      if (!resp.ok) {
        const errorText = await resp.text();
        this.mensajeError.set('Error al enviar la solicitud: ' + errorText);
        this.enviando.set(false);
        return;
      }

      const data = await resp.json();
      this.confirmacion.set({ id: data.id, estado: data.estado });
      // Limpiar formulario
      this.cedula.set('');
      this.nombres.set('');
      this.telefono.set('');
      this.correoElectronico.set('');
      this.fechaNacimiento.set('');
      this.nivelEstudios.set('');
      this.errores.set({});

    } catch (error) {
      this.mensajeError.set('Error de red al enviar la solicitud.');
    } finally {
      this.enviando.set(false);
    }
  }
}