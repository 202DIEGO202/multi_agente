import { Component, signal, computed, effect } from '@angular/core';
import { FormsModule } from '@angular/forms';

interface Solicitud {
  cedula: string;
  nombres: string;
  telefono: string;
  correo_electronico: string;
  fecha_nacimiento: string; // YYYY-MM-DD
  nivel_estudios: string;
}

interface Errores {
  cedula?: string;
  nombres?: string;
  telefono?: string;
  correo_electronico?: string;
  fecha_nacimiento?: string;
  nivel_estudios?: string;
  general?: string;
}

const nivelesValidos = [
  'Primaria',
  'Secundaria',
  'Bachillerato',
  'Técnico',
  'Tecnológico',
  'Universitario',
  'Posgrado'
];

@Component({
  selector: 'solicitud-form',
  standalone: true,
  imports: [FormsModule],
  template: `
    <section class="card">
      <h1>Solicitud de creación de usuario corporativo</h1>
      <form (ngSubmit)="enviarSolicitud()" #form="ngForm" novalidate>
        <label class="field">Cédula
          <input name="cedula" [(ngModel)]="solicitud.cedula" required #cedula="ngModel" />
        </label>
        <div *ngIf="errores().cedula" class="error">{{ errores().cedula }}</div>

        <label class="field">Nombres completos
          <input name="nombres" [(ngModel)]="solicitud.nombres" required #nombres="ngModel" />
        </label>
        <div *ngIf="errores().nombres" class="error">{{ errores().nombres }}</div>

        <label class="field">Teléfono
          <input name="telefono" [(ngModel)]="solicitud.telefono" required #telefono="ngModel" />
        </label>
        <div *ngIf="errores().telefono" class="error">{{ errores().telefono }}</div>

        <label class="field">Correo electrónico
          <input name="correo_electronico" type="email" [(ngModel)]="solicitud.correo_electronico" required #correo="ngModel" />
        </label>
        <div *ngIf="errores().correo_electronico" class="error">{{ errores().correo_electronico }}</div>

        <label class="field">Fecha de nacimiento
          <input name="fecha_nacimiento" type="date" [(ngModel)]="solicitud.fecha_nacimiento" required #fecha="ngModel" />
        </label>
        <div *ngIf="errores().fecha_nacimiento" class="error">{{ errores().fecha_nacimiento }}</div>

        <label class="field">Nivel de estudios
          <select name="nivel_estudios" [(ngModel)]="solicitud.nivel_estudios" required #nivel="ngModel">
            <option value="" disabled selected>Seleccione nivel</option>
            <option *ngFor="let nivel of niveles" [value]="nivel">{{ nivel }}</option>
          </select>
        </label>
        <div *ngIf="errores().nivel_estudios" class="error">{{ errores().nivel_estudios }}</div>

        <div *ngIf="errores().general" class="error">{{ errores().general }}</div>

        <div class="actions">
          <button type="submit" [disabled]="enviando()">Enviar solicitud</button>
        </div>
      </form>

      <section *ngIf="confirmacion()" class="success">
        <p>Solicitud enviada con ID: <strong>{{ confirmacion()?.id }}</strong></p>
        <p>Estado: <strong>{{ confirmacion()?.estado }}</strong></p>
      </section>
    </section>
  `
})
export class SolicitudFormComponent {
  niveles = nivelesValidos;

  solicitud = signal<Solicitud>({
    cedula: '',
    nombres: '',
    telefono: '',
    correo_electronico: '',
    fecha_nacimiento: '',
    nivel_estudios: ''
  });

  errores = signal<Errores>({});
  enviando = signal(false);
  confirmacion = signal<{id: number; estado: string} | null>(null);

  // Validar campos y reglas de negocio
  validar(): boolean {
    const s = this.solicitud();
    const e: Errores = {};

    // Validar obligatorios
    if (!s.cedula.trim()) e.cedula = 'Cédula es obligatoria';
    if (!s.nombres.trim()) e.nombres = 'Nombres completos son obligatorios';
    if (!s.telefono.trim()) e.telefono = 'Teléfono es obligatorio';
    if (!s.correo_electronico.trim()) {
      e.correo_electronico = 'Correo electrónico es obligatorio';
    } else {
      // Validar formato email simple
      const emailRegex = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
      if (!emailRegex.test(s.correo_electronico)) {
        e.correo_electronico = 'Correo electrónico no es válido';
      }
    }
    if (!s.fecha_nacimiento) {
      e.fecha_nacimiento = 'Fecha de nacimiento es obligatoria';
    } else {
      // Validar edad > 23
      const hoy = new Date();
      const fn = new Date(s.fecha_nacimiento);
      if (isNaN(fn.getTime())) {
        e.fecha_nacimiento = 'Fecha de nacimiento no es válida';
      } else {
        let edad = hoy.getFullYear() - fn.getFullYear();
        const m = hoy.getMonth() - fn.getMonth();
        if (m < 0 || (m === 0 && hoy.getDate() < fn.getDate())) {
          edad--;
        }
        if (edad <= 23) {
          e.fecha_nacimiento = 'La edad debe ser mayor a 23 años';
        }
      }
    }

    if (!s.nivel_estudios) {
      e.nivel_estudios = 'Nivel de estudios es obligatorio';
    } else {
      // Validar nivel mínimo bachillerato
      const nivelesOrden = {
        'Primaria': 1,
        'Secundaria': 2,
        'Bachillerato': 3,
        'Técnico': 4,
        'Tecnológico': 5,
        'Universitario': 6,
        'Posgrado': 7
      };
      if (!nivelesOrden.hasOwnProperty(s.nivel_estudios)) {
        e.nivel_estudios = 'Nivel de estudios no es válido';
      } else if (nivelesOrden[s.nivel_estudios] < nivelesOrden['Bachillerato']) {
        e.nivel_estudios = 'Nivel de estudios mínimo: bachillerato';
      }
    }

    this.errores.set(e);
    return Object.keys(e).length === 0;
  }

  async enviarSolicitud() {
    if (!this.validar()) {
      return;
    }
    this.enviando.set(true);
    this.confirmacion.set(null);

    try {
      const s = this.solicitud();
      const response = await fetch('/api/solicitudes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(s)
      });
      if (!response.ok) {
        const text = await response.text();
        this.errores.set({ general: `Error al enviar solicitud: ${response.status} ${text}` });
      } else {
        const data = await response.json();
        this.confirmacion.set({ id: data.id, estado: data.estado });
        // Limpiar formulario
        this.solicitud.set({ cedula: '', nombres: '', telefono: '', correo_electronico: '', fecha_nacimiento: '', nivel_estudios: '' });
        this.errores.set({});
      }
    } catch (error) {
      this.errores.set({ general: 'Error de red al enviar solicitud' });
    } finally {
      this.enviando.set(false);
    }
  }
}