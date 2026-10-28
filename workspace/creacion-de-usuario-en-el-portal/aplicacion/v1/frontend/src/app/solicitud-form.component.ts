import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, NgForm } from '@angular/forms';

const nivelesValidos = ['bachillerato', 'tecnico', 'tecnologo', 'profesional', 'especializacion', 'maestria', 'doctorado'];

@Component({
  selector: 'app-solicitud-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <h2>Crear Solicitud de Usuario Corporativo</h2>
    <form #form="ngForm" (ngSubmit)="enviarSolicitud(form)" novalidate>
      <label for="cedula">Cédula:</label><br />
      <input id="cedula" name="cedula" type="text" required minlength="5" maxlength="20" [(ngModel)]="cedula" #cedulaCtrl="ngModel" />
      <div *ngIf="cedulaCtrl.invalid && (cedulaCtrl.dirty || cedulaCtrl.touched)" style="color:red; font-size:0.9em">
        <div *ngIf="cedulaCtrl.errors?.['required']">La cédula es obligatoria.</div>
        <div *ngIf="cedulaCtrl.errors?.['minlength']">Mínimo 5 caracteres.</div>
        <div *ngIf="cedulaCtrl.errors?.['maxlength']">Máximo 20 caracteres.</div>
      </div>

      <label for="nombres">Nombres:</label><br />
      <input id="nombres" name="nombres" type="text" required minlength="3" maxlength="100" [(ngModel)]="nombres" #nombresCtrl="ngModel" />
      <div *ngIf="nombresCtrl.invalid && (nombresCtrl.dirty || nombresCtrl.touched)" style="color:red; font-size:0.9em">
        <div *ngIf="nombresCtrl.errors?.['required']">Los nombres son obligatorios.</div>
        <div *ngIf="nombresCtrl.errors?.['minlength']">Mínimo 3 caracteres.</div>
        <div *ngIf="nombresCtrl.errors?.['maxlength']">Máximo 100 caracteres.</div>
      </div>

      <label for="telefono">Teléfono:</label><br />
      <input id="telefono" name="telefono" type="tel" required pattern="^[0-9+\-\s]{7,20}$" [(ngModel)]="telefono" #telefonoCtrl="ngModel" />
      <div *ngIf="telefonoCtrl.invalid && (telefonoCtrl.dirty || telefonoCtrl.touched)" style="color:red; font-size:0.9em">
        <div *ngIf="telefonoCtrl.errors?.['required']">El teléfono es obligatorio.</div>
        <div *ngIf="telefonoCtrl.errors?.['pattern']">Formato de teléfono inválido.</div>
      </div>

      <label for="correo_electronico">Correo Electrónico:</label><br />
      <input id="correo_electronico" name="correo_electronico" type="email" required [(ngModel)]="correo_electronico" #correoCtrl="ngModel" />
      <div *ngIf="correoCtrl.invalid && (correoCtrl.dirty || correoCtrl.touched)" style="color:red; font-size:0.9em">
        <div *ngIf="correoCtrl.errors?.['required']">El correo es obligatorio.</div>
        <div *ngIf="correoCtrl.errors?.['email']">Correo inválido.</div>
      </div>

      <label for="fecha_nacimiento">Fecha de Nacimiento:</label><br />
      <input id="fecha_nacimiento" name="fecha_nacimiento" type="date" required [(ngModel)]="fecha_nacimiento" #fechaCtrl="ngModel" />
      <div *ngIf="fechaCtrl.invalid && (fechaCtrl.dirty || fechaCtrl.touched)" style="color:red; font-size:0.9em">
        <div *ngIf="fechaCtrl.errors?.['required']">La fecha de nacimiento es obligatoria.</div>
      </div>

      <label for="nivel_estudios">Nivel de Estudios:</label><br />
      <select id="nivel_estudios" name="nivel_estudios" required [(ngModel)]="nivel_estudios" #nivelCtrl="ngModel">
        <option value="" disabled selected>Seleccione nivel</option>
        <option value="bachillerato">Bachillerato</option>
        <option value="tecnico">Técnico</option>
        <option value="tecnologo">Tecnólogo</option>
        <option value="profesional">Profesional</option>
        <option value="especializacion">Especialización</option>
        <option value="maestria">Maestría</option>
        <option value="doctorado">Doctorado</option>
      </select>
      <div *ngIf="nivelCtrl.invalid && (nivelCtrl.dirty || nivelCtrl.touched)" style="color:red; font-size:0.9em">
        <div *ngIf="nivelCtrl.errors?.['required']">El nivel de estudios es obligatorio.</div>
      </div>

      <div *ngIf="errorEdad" style="color:red; font-size:0.9em; margin-top:0.5rem">La edad debe ser mayor a 23 años.</div>
      <div *ngIf="errorNivel" style="color:red; font-size:0.9em; margin-top:0.5rem">Nivel de estudios mínimo: bachillerato.</div>
      <div *ngIf="errorEnvio" style="color:red; font-size:0.9em; margin-top:0.5rem">{{errorEnvio}}</div>
      <div *ngIf="exitoEnvio" style="color:green; font-size:1em; margin-top:0.5rem">Solicitud enviada correctamente.</div>

      <button type="submit" [disabled]="form.invalid || errorEdad || errorNivel" style="margin-top:1rem; padding:0.5rem 1rem;">Enviar Solicitud</button>
    </form>
  `
})
export class SolicitudFormComponent {
  cedula = '';
  nombres = '';
  telefono = '';
  correo_electronico = '';
  fecha_nacimiento = '';
  nivel_estudios = '';

  errorEdad = false;
  errorNivel = false;
  errorEnvio = '';
  exitoEnvio = false;

  private calcularEdad(fecha: string): number {
    const hoy = new Date();
    const nac = new Date(fecha);
    let edad = hoy.getFullYear() - nac.getFullYear();
    const m = hoy.getMonth() - nac.getMonth();
    if (m < 0 || (m === 0 && hoy.getDate() < nac.getDate())) {
      edad--;
    }
    return edad;
  }

  private validarEdadYNivel(): void {
    this.errorEdad = false;
    this.errorNivel = false;
    if (this.fecha_nacimiento) {
      const edad = this.calcularEdad(this.fecha_nacimiento);
      if (edad <= 23) {
        this.errorEdad = true;
      }
    } else {
      this.errorEdad = true;
    }
    // Validar nivel estudios mínimo bachillerato
    if (!this.nivel_estudios || nivelesValidos.indexOf(this.nivel_estudios.toLowerCase()) < 0) {
      this.errorNivel = true;
    } else {
      // nivel mínimo es bachillerato, que es el primer en la lista
      const indice = nivelesValidos.indexOf(this.nivel_estudios.toLowerCase());
      const indiceMin = nivelesValidos.indexOf('bachillerato');
      if (indice < indiceMin) {
        this.errorNivel = true;
      }
    }
  }

  async enviarSolicitud(form: NgForm) {
    this.errorEnvio = '';
    this.exitoEnvio = false;
    this.validarEdadYNivel();
    if (form.invalid || this.errorEdad || this.errorNivel) {
      return;
    }
    try {
      const body = {
        cedula: this.cedula.trim(),
        nombres: this.nombres.trim(),
        telefono: this.telefono.trim(),
        correo_electronico: this.correo_electronico.trim(),
        fecha_nacimiento: this.fecha_nacimiento,
        nivel_estudios: this.nivel_estudios
      };
      const res = await fetch('/api/solicitudes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        this.errorEnvio = err.mensaje || 'Error al enviar la solicitud';
        return;
      }
      this.exitoEnvio = true;
      form.resetForm();
    } catch {
      this.errorEnvio = 'Error de conexión al enviar la solicitud';
    }
  }
}