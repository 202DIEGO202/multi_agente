import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, NgForm } from '@angular/forms';

@Component({
  selector: 'app-solicitud-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <h2>Solicitud de creación de usuario</h2>
    <form #form="ngForm" (ngSubmit)="enviarSolicitud(form)" novalidate>
      <label class="field">Cédula
        <input name="cedula" [(ngModel)]="cedula" required #cedulaRef="ngModel" />
      </label>
      <div *ngIf="cedulaRef.invalid && cedulaRef.touched" class="error">Cédula es requerida.</div>

      <label class="field">Nombres
        <input name="nombres" [(ngModel)]="nombres" required #nombresRef="ngModel" />
      </label>
      <div *ngIf="nombresRef.invalid && nombresRef.touched" class="error">Nombres son requeridos.</div>

      <label class="field">Teléfono
        <input name="telefono" [(ngModel)]="telefono" required #telefonoRef="ngModel" />
      </label>
      <div *ngIf="telefonoRef.invalid && telefonoRef.touched" class="error">Teléfono es requerido.</div>

      <label class="field">Correo electrónico
        <input name="correo_electronico" [(ngModel)]="correo_electronico" required email #correoRef="ngModel" />
      </label>
      <div *ngIf="correoRef.invalid && correoRef.touched" class="error">
        <div *ngIf="correoRef.errors?.['required']">Correo es requerido.</div>
        <div *ngIf="correoRef.errors?.['email']">Correo no es válido.</div>
      </div>

      <label class="field">Fecha de nacimiento
        <input type="date" name="fecha_nacimiento" [(ngModel)]="fecha_nacimiento" required #fechaRef="ngModel" />
      </label>
      <div *ngIf="fechaRef.invalid && fechaRef.touched" class="error">Fecha de nacimiento es requerida.</div>

      <label class="field">Nivel de estudios
        <select name="nivel_estudios" [(ngModel)]="nivel_estudios" required #nivelRef="ngModel">
          <option value="">Seleccione</option>
          <option value="primaria">Primaria</option>
          <option value="bachillerato">Bachillerato</option>
          <option value="tecnico">Técnico</option>
          <option value="tecnologo">Tecnólogo</option>
          <option value="profesional">Profesional</option>
          <option value="posgrado">Posgrado</option>
        </select>
      </label>
      <div *ngIf="nivelRef.invalid && nivelRef.touched" class="error">Nivel de estudios es requerido.</div>

      <div *ngIf="errorEdad" class="error">La edad debe ser mayor a 23 años.</div>
      <div *ngIf="errorNivel" class="error">Nivel de estudios mínimo: bachillerato.</div>

      <button type="submit" [disabled]="form.invalid || errorEdad || errorNivel">Enviar solicitud</button>

      <div *ngIf="mensaje" [class.success]="exito" [class.error]="!exito" class="alert">{{mensaje}}</div>
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

  mensaje = '';
  exito = false;

  private nivelesValidos = ['bachillerato', 'tecnico', 'tecnologo', 'profesional', 'posgrado'];

  calcularEdad(fecha: string): number {
    const hoy = new Date();
    const nac = new Date(fecha);
    let edad = hoy.getFullYear() - nac.getFullYear();
    const m = hoy.getMonth() - nac.getMonth();
    if (m < 0 || (m === 0 && hoy.getDate() < nac.getDate())) {
      edad--;
    }
    return edad;
  }

  validarEdad(): boolean {
    if (!this.fecha_nacimiento) return false;
    const edad = this.calcularEdad(this.fecha_nacimiento);
    this.errorEdad = edad <= 23;
    return !this.errorEdad;
  }

  validarNivel(): boolean {
    this.errorNivel = !this.nivelesValidos.includes(this.nivel_estudios.toLowerCase());
    return !this.errorNivel;
  }

  async enviarSolicitud(form: NgForm) {
    this.mensaje = '';
    this.exito = false;

    const edadValida = this.validarEdad();
    const nivelValido = this.validarNivel();

    if (!form.valid || !edadValida || !nivelValido) {
      this.mensaje = 'Corrija los errores antes de enviar la solicitud.';
      return;
    }

    const body = {
      cedula: this.cedula.trim(),
      nombres: this.nombres.trim(),
      telefono: this.telefono.trim(),
      correo_electronico: this.correo_electronico.trim(),
      fecha_nacimiento: this.fecha_nacimiento,
      nivel_estudios: this.nivel_estudios
    };

    try {
      const res = await fetch('/api/solicitudes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (!res.ok) {
        const errorText = await res.text();
        this.mensaje = `Error al enviar solicitud: ${errorText}`;
        return;
      }
      this.mensaje = 'Solicitud enviada correctamente.';
      this.exito = true;
      form.resetForm();
    } catch (e) {
      this.mensaje = 'Error de conexión al enviar la solicitud.';
    }
  }
}