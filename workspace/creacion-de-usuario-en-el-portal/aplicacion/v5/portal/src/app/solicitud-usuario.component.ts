import { Component, signal } from '@angular/core';

interface FormState {
  cedula: string;
  nombres: string;
  telefono: string;
  correo_electronico: string;
  fecha_nacimiento: string;
  nivel_estudios: string;
}

interface FormErrors {
  cedula?: string;
  nombres?: string;
  telefono?: string;
  correo_electronico?: string;
  fecha_nacimiento?: string;
  nivel_estudios?: string;
  general?: string;
}

interface RespuestaEnvio {
  id: number;
  estado: string;
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

const nivelMinimoIndex = nivelesValidos.indexOf('Bachillerato');

@Component({
  selector: 'app-solicitud-usuario',
  standalone: true,
  template: `
    <section class="card">
      <h1>Solicitud de creación de usuario corporativo</h1>
      <form (submit)="enviarSolicitud($event)" novalidate>
        <label class="field">Cédula <input type="text" [value]="form().cedula" (input)="setField('cedula', $any($event.target).value)" required></label>
        <div *ngIf="errors().cedula" class="error">{{errors().cedula}}</div>

        <label class="field">Nombres completos <input type="text" [value]="form().nombres" (input)="setField('nombres', $any($event.target).value)" required></label>
        <div *ngIf="errors().nombres" class="error">{{errors().nombres}}</div>

        <label class="field">Teléfono <input type="text" [value]="form().telefono" (input)="setField('telefono', $any($event.target).value)" required></label>
        <div *ngIf="errors().telefono" class="error">{{errors().telefono}}</div>

        <label class="field">Correo electrónico <input type="email" [value]="form().correo_electronico" (input)="setField('correo_electronico', $any($event.target).value)" required></label>
        <div *ngIf="errors().correo_electronico" class="error">{{errors().correo_electronico}}</div>

        <label class="field">Fecha de nacimiento <input type="date" [value]="form().fecha_nacimiento" (input)="setField('fecha_nacimiento', $any($event.target).value)" required></label>
        <div *ngIf="errors().fecha_nacimiento" class="error">{{errors().fecha_nacimiento}}</div>

        <label class="field">Nivel de estudios
          <select [value]="form().nivel_estudios" (change)="setField('nivel_estudios', $any($event.target).value)" required>
            <option value="">Seleccione</option>
            <option *ngFor="let nivel of niveles" [value]="nivel">{{nivel}}</option>
          </select>
        </label>
        <div *ngIf="errors().nivel_estudios" class="error">{{errors().nivel_estudios}}</div>

        <div *ngIf="errors().general" class="error">{{errors().general}}</div>

        <div class="actions">
          <button type="submit" [disabled]="enviando()">Enviar solicitud</button>
        </div>
      </form>

      <section *ngIf="respuesta()" class="success">
        <p>Solicitud enviada con ID: <strong>{{respuesta()?.id}}</strong></p>
        <p>Estado: <strong>{{respuesta()?.estado}}</strong></p>
      </section>
    </section>
  `
})
export class SolicitudUsuarioComponent {
  niveles = nivelesValidos;

  private formSignal = signal<FormState>({
    cedula: '',
    nombres: '',
    telefono: '',
    correo_electronico: '',
    fecha_nacimiento: '',
    nivel_estudios: ''
  });
  form = this.formSignal.asReadonly();

  private errorsSignal = signal<FormErrors>({});
  errors = this.errorsSignal.asReadonly();

  private enviandoSignal = signal(false);
  enviando = this.enviandoSignal.asReadonly();

  private respuestaSignal = signal<RespuestaEnvio | null>(null);
  respuesta = this.respuestaSignal.asReadonly();

  setField(field: keyof FormState, value: string) {
    this.formSignal.update(f => ({ ...f, [field]: value }));
    this.errorsSignal.update(e => {
      const copy = { ...e };
      delete copy[field];
      delete copy.general;
      return copy;
    });
    this.respuestaSignal.set(null); // limpiar respuesta al cambiar
  }

  validar(): boolean {
    const f = this.formSignal();
    const e: FormErrors = {};

    // Validar campos obligatorios
    if (!f.cedula.trim()) e.cedula = 'Cédula es obligatoria';
    if (!f.nombres.trim()) e.nombres = 'Nombres completos son obligatorios';
    if (!f.telefono.trim()) e.telefono = 'Teléfono es obligatorio';
    if (!f.correo_electronico.trim()) {
      e.correo_electronico = 'Correo electrónico es obligatorio';
    } else {
      // Validar formato básico email
      const emailRegex = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
      if (!emailRegex.test(f.correo_electronico)) {
        e.correo_electronico = 'Correo electrónico no es válido';
      }
    }
    if (!f.fecha_nacimiento.trim()) {
      e.fecha_nacimiento = 'Fecha de nacimiento es obligatoria';
    } else {
      // Validar edad > 23
      const fecha = new Date(f.fecha_nacimiento);
      if (isNaN(fecha.getTime())) {
        e.fecha_nacimiento = 'Fecha de nacimiento no es válida';
      } else {
        const hoy = new Date();
        let edad = hoy.getFullYear() - fecha.getFullYear();
        const m = hoy.getMonth() - fecha.getMonth();
        if (m < 0 || (m === 0 && hoy.getDate() < fecha.getDate())) {
          edad--;
        }
        if (edad <= 23) {
          e.fecha_nacimiento = 'La edad debe ser mayor a 23 años';
        }
      }
    }

    if (!f.nivel_estudios.trim()) {
      e.nivel_estudios = 'Nivel de estudios es obligatorio';
    } else {
      const idx = nivelesValidos.indexOf(f.nivel_estudios);
      if (idx < nivelMinimoIndex) {
        e.nivel_estudios = 'Nivel de estudios mínimo: bachillerato';
      }
    }

    this.errorsSignal.set(e);
    return Object.keys(e).length === 0;
  }

  async enviarSolicitud(event: Event) {
    event.preventDefault();
    this.respuestaSignal.set(null);
    if (!this.validar()) {
      return;
    }
    this.enviandoSignal.set(true);
    const f = this.formSignal();
    try {
      const resp = await fetch('/api/solicitudes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cedula: f.cedula.trim(),
          nombres: f.nombres.trim(),
          telefono: f.telefono.trim(),
          correo_electronico: f.correo_electronico.trim(),
          fecha_nacimiento: f.fecha_nacimiento,
          nivel_estudios: f.nivel_estudios
        })
      });
      if (!resp.ok) {
        const text = await resp.text();
        this.errorsSignal.update(e => ({ ...e, general: `Error al enviar solicitud: ${resp.status} ${text}` }));
      } else {
        const data = await resp.json();
        this.respuestaSignal.set({ id: data.id, estado: data.estado });
        // Limpiar formulario
        this.formSignal.set({ cedula: '', nombres: '', telefono: '', correo_electronico: '', fecha_nacimiento: '', nivel_estudios: '' });
        this.errorsSignal.set({});
      }
    } catch (error) {
      this.errorsSignal.update(e => ({ ...e, general: 'Error de red al enviar solicitud' }));
    } finally {
      this.enviandoSignal.set(false);
    }
  }
}