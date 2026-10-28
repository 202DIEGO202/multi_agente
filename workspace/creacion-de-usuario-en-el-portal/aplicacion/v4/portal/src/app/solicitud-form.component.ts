import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';

const nivelesValidos = ['Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado'];

@Component({
  selector: 'solicitud-form',
  standalone: true,
  imports: [CommonModule],
  template: `
    <h1>Solicitud de creación de usuario corporativo</h1>

    <form (submit)="onSubmit($event)" novalidate class="card">
      <label class="field">Cédula
        <input type="text" [value]="cedula()" (input)="cedula.set($any($event.target).value)" required>
      </label>
      <div *ngIf="errorCedula()" class="error">{{errorCedula()}}</div>

      <label class="field">Nombres completos
        <input type="text" [value]="nombres()" (input)="nombres.set($any($event.target).value)" required>
      </label>
      <div *ngIf="errorNombres()" class="error">{{errorNombres()}}</div>

      <label class="field">Teléfono
        <input type="tel" [value]="telefono()" (input)="telefono.set($any($event.target).value)" required>
      </label>
      <div *ngIf="errorTelefono()" class="error">{{errorTelefono()}}</div>

      <label class="field">Correo electrónico
        <input type="email" [value]="correo()" (input)="correo.set($any($event.target).value)" required>
      </label>
      <div *ngIf="errorCorreo()" class="error">{{errorCorreo()}}</div>

      <label class="field">Fecha de nacimiento
        <input type="date" [value]="fechaNacimiento()" (input)="fechaNacimiento.set($any($event.target).value)" required>
      </label>
      <div *ngIf="errorFechaNacimiento()" class="error">{{errorFechaNacimiento()}}</div>

      <label class="field">Nivel de estudios
        <select [value]="nivelEstudios()" (change)="nivelEstudios.set($any($event.target).value)" required>
          <option value="">Seleccione</option>
          <option *ngFor="let nivel of niveles" [value]="nivel">{{nivel}}</option>
        </select>
      </label>
      <div *ngIf="errorNivelEstudios()" class="error">{{errorNivelEstudios()}}</div>

      <div *ngIf="mensajeError()" class="error">{{mensajeError()}}</div>

      <div class="actions">
        <button type="submit" [disabled]="!formValido()">Enviar solicitud</button>
      </div>

      <div *ngIf="confirmacion()" class="success">
        Solicitud enviada con ID: {{confirmacion().id}} - Estado: {{confirmacion().estado}}
      </div>
    </form>
  `
})
export class SolicitudFormComponent {
  cedula = signal('');
  nombres = signal('');
  telefono = signal('');
  correo = signal('');
  fechaNacimiento = signal('');
  nivelEstudios = signal('');

  errorCedula = signal('');
  errorNombres = signal('');
  errorTelefono = signal('');
  errorCorreo = signal('');
  errorFechaNacimiento = signal('');
  errorNivelEstudios = signal('');
  mensajeError = signal('');

  confirmacion = signal<{id:number, estado:string} | null>(null);

  niveles = nivelesValidos;

  validarCedula(value: string): string {
    if (!value.trim()) return 'Cédula es obligatoria';
    return '';
  }

  validarNombres(value: string): string {
    if (!value.trim()) return 'Nombres completos son obligatorios';
    return '';
  }

  validarTelefono(value: string): string {
    if (!value.trim()) return 'Teléfono es obligatorio';
    return '';
  }

  validarCorreo(value: string): string {
    if (!value.trim()) return 'Correo electrónico es obligatorio';
    // Simple email regex
    const re = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
    if (!re.test(value)) return 'Correo electrónico no es válido';
    return '';
  }

  validarFechaNacimiento(value: string): string {
    if (!value) return 'Fecha de nacimiento es obligatoria';
    const fecha = new Date(value);
    if (isNaN(fecha.getTime())) return 'Fecha de nacimiento no es válida';
    const hoy = new Date();
    let edad = hoy.getFullYear() - fecha.getFullYear();
    const m = hoy.getMonth() - fecha.getMonth();
    if (m < 0 || (m === 0 && hoy.getDate() < fecha.getDate())) {
      edad--;
    }
    if (edad <= 23) return 'La edad debe ser mayor a 23 años';
    return '';
  }

  validarNivelEstudios(value: string): string {
    if (!value) return 'Nivel de estudios es obligatorio';
    if (!nivelesValidos.includes(value)) return 'Nivel de estudios mínimo: bachillerato';
    return '';
  }

  validarFormulario(): boolean {
    const ced = this.cedula();
    const nom = this.nombres();
    const tel = this.telefono();
    const cor = this.correo();
    const fnac = this.fechaNacimiento();
    const nivel = this.nivelEstudios();

    this.errorCedula.set(this.validarCedula(ced));
    this.errorNombres.set(this.validarNombres(nom));
    this.errorTelefono.set(this.validarTelefono(tel));
    this.errorCorreo.set(this.validarCorreo(cor));
    this.errorFechaNacimiento.set(this.validarFechaNacimiento(fnac));
    this.errorNivelEstudios.set(this.validarNivelEstudios(nivel));

    return !this.errorCedula() && !this.errorNombres() && !this.errorTelefono() && !this.errorCorreo() && !this.errorFechaNacimiento() && !this.errorNivelEstudios();
  }

  formValido() {
    return this.validarFormulario();
  }

  async onSubmit(event: Event) {
    event.preventDefault();
    this.mensajeError.set('');
    this.confirmacion.set(null);

    if (!this.validarFormulario()) {
      this.mensajeError.set('Por favor corrija los errores antes de enviar.');
      return;
    }

    // Preparar datos
    const data = {
      cedula: this.cedula().trim(),
      nombres_completos: this.nombres().trim(),
      telefono: this.telefono().trim(),
      correo_electronico: this.correo().trim(),
      fecha_nacimiento: this.fechaNacimiento(),
      nivel_estudios: this.nivelEstudios()
    };

    try {
      const response = await fetch('/api/solicitudes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.mensajeError.set(`Error al enviar la solicitud: ${errorText}`);
        return;
      }

      const result = await response.json();
      this.confirmacion.set(result);

      // Limpiar formulario
      this.cedula.set('');
      this.nombres.set('');
      this.telefono.set('');
      this.correo.set('');
      this.fechaNacimiento.set('');
      this.nivelEstudios.set('');

    } catch (error) {
      this.mensajeError.set('Error de conexión al enviar la solicitud.');
    }
  }
}