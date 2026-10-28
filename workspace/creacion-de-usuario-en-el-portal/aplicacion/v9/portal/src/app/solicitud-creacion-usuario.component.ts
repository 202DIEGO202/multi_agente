import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

interface Solicitud {
  cedula: string;
  nombres_completos: string;
  telefono: string;
  correo_electronico: string;
  fecha_nacimiento: string; // ISO string yyyy-MM-dd
  nivel_estudios: string;
}

interface Errores {
  cedula?: string;
  nombres_completos?: string;
  telefono?: string;
  correo_electronico?: string;
  fecha_nacimiento?: string;
  nivel_estudios?: string;
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
        <input name="cedula" [(ngModel)]="solicitud().cedula" required #cedula="ngModel" />
      </label>
      <div *ngIf="errores().cedula" class="error">{{ errores().cedula }}</div>

      <label class="field">Nombres completos *
        <input name="nombres_completos" [(ngModel)]="solicitud().nombres_completos" required #nombres="ngModel" />
      </label>
      <div *ngIf="errores().nombres_completos" class="error">{{ errores().nombres_completos }}</div>

      <label class="field">Teléfono *
        <input name="telefono" [(ngModel)]="solicitud().telefono" required #telefono="ngModel" />
      </label>
      <div *ngIf="errores().telefono" class="error">{{ errores().telefono }}</div>

      <label class="field">Correo electrónico *
        <input name="correo_electronico" type="email" [(ngModel)]="solicitud().correo_electronico" required #correo="ngModel" />
      </label>
      <div *ngIf="errores().correo_electronico" class="error">{{ errores().correo_electronico }}</div>

      <label class="field">Fecha de nacimiento *
        <input name="fecha_nacimiento" type="date" [(ngModel)]="solicitud().fecha_nacimiento" required #fecha="ngModel" />
      </label>
      <div *ngIf="errores().fecha_nacimiento" class="error">{{ errores().fecha_nacimiento }}</div>

      <label class="field">Nivel de estudios *
        <select name="nivel_estudios" [(ngModel)]="solicitud().nivel_estudios" required #nivel="ngModel">
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
      <div *ngIf="errores().nivel_estudios" class="error">{{ errores().nivel_estudios }}</div>

      <div *ngIf="errores().general" class="error">{{ errores().general }}</div>

      <div class="actions">
        <button type="submit" [disabled]="enviando()">Enviar solicitud</button>
      </div>

      <div *ngIf="confirmacion()" class="success">
        Solicitud enviada con ID: {{ confirmacion()?.id }} - Estado: {{ confirmacion()?.estado }}
      </div>
    </form>
  </main>
  `
})
export class SolicitudCreacionUsuarioComponent {
  solicitud = signal<Solicitud>({
    cedula: '',
    nombres_completos: '',
    telefono: '',
    correo_electronico: '',
    fecha_nacimiento: '',
    nivel_estudios: ''
  });

  errores = signal<Errores>({});
  enviando = signal(false);
  confirmacion = signal<{id: number; estado: string} | null>(null);

  private nivelesValidos = ['Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado'];

  private calcularEdad(fechaNacimiento: string): number {
    if (!fechaNacimiento) return 0;
    const hoy = new Date();
    const nacimiento = new Date(fechaNacimiento);
    let edad = hoy.getFullYear() - nacimiento.getFullYear();
    const m = hoy.getMonth() - nacimiento.getMonth();
    if (m < 0 || (m === 0 && hoy.getDate() < nacimiento.getDate())) {
      edad--;
    }
    return edad;
  }

  private validar(): boolean {
    const s = this.solicitud();
    const e: Errores = {};

    // Validar campos obligatorios
    if (!s.cedula.trim()) e.cedula = 'Cédula es obligatoria';
    if (!s.nombres_completos.trim()) e.nombres_completos = 'Nombres completos son obligatorios';
    if (!s.telefono.trim()) e.telefono = 'Teléfono es obligatorio';
    if (!s.correo_electronico.trim()) {
      e.correo_electronico = 'Correo electrónico es obligatorio';
    } else {
      // Validar formato email simple
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(s.correo_electronico)) {
        e.correo_electronico = 'Correo electrónico no es válido';
      }
    }
    if (!s.fecha_nacimiento) {
      e.fecha_nacimiento = 'Fecha de nacimiento es obligatoria';
    } else {
      const edad = this.calcularEdad(s.fecha_nacimiento);
      if (edad <= 23) {
        e.fecha_nacimiento = 'La edad debe ser mayor a 23 años';
      }
    }
    if (!s.nivel_estudios) {
      e.nivel_estudios = 'Nivel de estudios es obligatorio';
    } else if (!this.nivelesValidos.includes(s.nivel_estudios)) {
      e.nivel_estudios = 'Nivel de estudios mínimo: bachillerato';
    }

    this.errores.set(e);
    return Object.keys(e).length === 0;
  }

  async enviarSolicitud() {
    if (!this.validar()) {
      return;
    }
    this.enviando.set(true);
    this.errores.set({});
    this.confirmacion.set(null);

    const s = this.solicitud();

    try {
      const response = await fetch('/api/solicitudes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cedula: s.cedula.trim(),
          nombres_completos: s.nombres_completos.trim(),
          telefono: s.telefono.trim(),
          correo_electronico: s.correo_electronico.trim(),
          fecha_nacimiento: s.fecha_nacimiento,
          nivel_estudios: s.nivel_estudios
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.errores.update(e => ({ ...e, general: `Error al enviar la solicitud: ${errorText}` }));
      } else {
        const data = await response.json();
        this.confirmacion.set({ id: data.id, estado: data.estado });
        // Limpiar formulario
        this.solicitud.set({ cedula: '', nombres_completos: '', telefono: '', correo_electronico: '', fecha_nacimiento: '', nivel_estudios: '' });
      }
    } catch (error) {
      this.errores.update(e => ({ ...e, general: 'Error de red al enviar la solicitud' }));
    } finally {
      this.enviando.set(false);
    }
  }
}