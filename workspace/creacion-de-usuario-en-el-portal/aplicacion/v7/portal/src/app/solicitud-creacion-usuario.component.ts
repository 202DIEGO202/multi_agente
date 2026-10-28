import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

interface FormData {
  cedula: string;
  nombresCompletos: string;
  telefono: string;
  correoElectronico: string;
  fechaNacimiento: string;
  nivelEstudios: string;
}

interface FormErrors {
  cedula?: string;
  nombresCompletos?: string;
  telefono?: string;
  correoElectronico?: string;
  fechaNacimiento?: string;
  nivelEstudios?: string;
  general?: string;
}

@Component({
  selector: 'app-solicitud-creacion-usuario',
  standalone: true,
  imports: [FormsModule],
  template: `
  <main class="card">
    <h1>Solicitud de creación de usuario corporativo</h1>
    <form (ngSubmit)="enviarSolicitud()" #form="ngForm" novalidate>
      <label class="field">Cédula *
        <input name="cedula" [(ngModel)]="formData.cedula" required #cedula="ngModel" />
      </label>
      <div *ngIf="errors().cedula" class="error">{{ errors().cedula }}</div>

      <label class="field">Nombres completos *
        <input name="nombresCompletos" [(ngModel)]="formData.nombresCompletos" required #nombresCompletos="ngModel" />
      </label>
      <div *ngIf="errors().nombresCompletos" class="error">{{ errors().nombresCompletos }}</div>

      <label class="field">Teléfono *
        <input name="telefono" [(ngModel)]="formData.telefono" required #telefono="ngModel" />
      </label>
      <div *ngIf="errors().telefono" class="error">{{ errors().telefono }}</div>

      <label class="field">Correo electrónico *
        <input name="correoElectronico" type="email" [(ngModel)]="formData.correoElectronico" required #correoElectronico="ngModel" />
      </label>
      <div *ngIf="errors().correoElectronico" class="error">{{ errors().correoElectronico }}</div>

      <label class="field">Fecha de nacimiento *
        <input name="fechaNacimiento" type="date" [(ngModel)]="formData.fechaNacimiento" required #fechaNacimiento="ngModel" />
      </label>
      <div *ngIf="errors().fechaNacimiento" class="error">{{ errors().fechaNacimiento }}</div>

      <label class="field">Nivel de estudios *
        <select name="nivelEstudios" [(ngModel)]="formData.nivelEstudios" required #nivelEstudios="ngModel">
          <option value="">--Seleccione--</option>
          <option>Primaria</option>
          <option>Secundaria</option>
          <option>Bachillerato</option>
          <option>Técnico</option>
          <option>Tecnológico</option>
          <option>Universitario</option>
          <option>Posgrado</option>
        </select>
      </label>
      <div *ngIf="errors().nivelEstudios" class="error">{{ errors().nivelEstudios }}</div>

      <div *ngIf="errors().general" class="error">{{ errors().general }}</div>

      <div class="actions">
        <button type="submit" [disabled]="enviando()">Enviar solicitud</button>
      </div>

      <div *ngIf="resultado()" class="success">
        Solicitud enviada con ID: {{ resultado()?.id }} - Estado: {{ resultado()?.estado }}
      </div>
    </form>
  </main>
  `
})
export class SolicitudCreacionUsuarioComponent {
  formData = signal<FormData>({
    cedula: '',
    nombresCompletos: '',
    telefono: '',
    correoElectronico: '',
    fechaNacimiento: '',
    nivelEstudios: ''
  });

  errors = signal<FormErrors>({});
  enviando = signal(false);
  resultado = signal<{id: number; estado: string} | null>(null);

  private nivelesValidos = ['Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado'];

  private calcularEdad(fecha: string): number {
    if (!fecha) return 0;
    const hoy = new Date();
    const nacimiento = new Date(fecha);
    let edad = hoy.getFullYear() - nacimiento.getFullYear();
    const m = hoy.getMonth() - nacimiento.getMonth();
    if (m < 0 || (m === 0 && hoy.getDate() < nacimiento.getDate())) {
      edad--;
    }
    return edad;
  }

  private validar(): boolean {
    const data = this.formData();
    const errs: FormErrors = {};

    // Validar campos obligatorios
    if (!data.cedula.trim()) errs.cedula = 'Cédula es obligatoria';
    if (!data.nombresCompletos.trim()) errs.nombresCompletos = 'Nombres completos son obligatorios';
    if (!data.telefono.trim()) errs.telefono = 'Teléfono es obligatorio';
    if (!data.correoElectronico.trim()) {
      errs.correoElectronico = 'Correo electrónico es obligatorio';
    } else {
      // Validar formato básico email
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(data.correoElectronico)) {
        errs.correoElectronico = 'Correo electrónico no es válido';
      }
    }
    if (!data.fechaNacimiento) {
      errs.fechaNacimiento = 'Fecha de nacimiento es obligatoria';
    } else {
      const edad = this.calcularEdad(data.fechaNacimiento);
      if (edad <= 23) {
        errs.fechaNacimiento = 'La edad debe ser mayor a 23 años';
      }
    }
    if (!data.nivelEstudios) {
      errs.nivelEstudios = 'Nivel de estudios es obligatorio';
    } else if (!this.nivelesValidos.includes(data.nivelEstudios)) {
      errs.nivelEstudios = 'Nivel de estudios mínimo: bachillerato';
    }

    this.errors.set(errs);
    return Object.keys(errs).length === 0;
  }

  async enviarSolicitud() {
    if (!this.validar()) {
      return;
    }
    this.enviando.set(true);
    this.errors.set({});
    this.resultado.set(null);

    const data = this.formData();

    try {
      const response = await fetch('/api/solicitudes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cedula: data.cedula.trim(),
          nombres_completos: data.nombresCompletos.trim(),
          telefono: data.telefono.trim(),
          correo_electronico: data.correoElectronico.trim(),
          fecha_nacimiento: data.fechaNacimiento,
          nivel_estudios: data.nivelEstudios
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.errors.set({ general: `Error al enviar la solicitud: ${errorText}` });
      } else {
        const json = await response.json();
        this.resultado.set({ id: json.id, estado: json.estado });
        // Limpiar formulario tras éxito
        this.formData.set({ cedula: '', nombresCompletos: '', telefono: '', correoElectronico: '', fechaNacimiento: '', nivelEstudios: '' });
      }
    } catch (e) {
      this.errors.set({ general: 'Error de conexión al enviar la solicitud' });
    } finally {
      this.enviando.set(false);
    }
  }
}