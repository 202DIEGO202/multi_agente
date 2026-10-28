import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'aprobacion-solicitud',
  standalone: true,
  imports: [CommonModule],
  template: `
    <h1>Aprobación de solicitud por líder de área</h1>

    <section class="card">
      <h2>Datos del solicitante</h2>
      <ul>
        <li>Nombre: Juan Pérez</li>
        <li>Cédula: 1234567890</li>
        <li>Área: Finanzas</li>
        <li>Cargo: Analista</li>
        <li>Fecha de nacimiento: 15/04/1985</li>
        <li>Edad: 39 años</li>
        <li>Nivel de estudios: Universitario</li>
      </ul>
    </section>

    <section class="card">
      <h2>Datos del líder de área (aprobador)</h2>
      <ul>
        <li>Nombre: Laura Gómez</li>
        <li>Cargo: Líder de área</li>
        <li>Área: Finanzas</li>
        <li>Correo electrónico: laura.gomez@empresa.com</li>
        <li>Fecha y hora de decisión: --/--/---- --:--</li>
      </ul>
    </section>

    <form (submit)="onSubmit($event)" novalidate class="card">
      <div class="actions">
        <button type="button" (click)="aprobar()">Aprobar solicitud</button>
        <button type="button" class="secondary" (click)="rechazar()">Rechazar solicitud</button>
      </div>

      <label class="field">Motivo de rechazo (obligatorio si rechaza)
        <input type="text" [value]="motivoRechazo()" (input)="setMotivoRechazo($any($event.target).value)" [disabled]="!rechazando()">
      </label>
      <div *ngIf="errorMotivo()" class="error">{{errorMotivo()}}</div>

      <div *ngIf="mensajeEstado()" class="alert" [class.error]="estado() === 'Rechazada'" [class.success]="estado() === 'Aprobada'">
        Estado de la aprobación: {{mensajeEstado()}}
      </div>
    </form>
  `
})
export class AprobacionSolicitudComponent {
  motivoRechazo = signal('');
  errorMotivo = signal('');
  mensajeEstado = signal('');
  estado = signal('');
  rechazando = signal(false);

  setMotivoRechazo(v: string) {
    this.motivoRechazo.set(v.trim());
    if (this.rechazando() && !v.trim()) {
      this.errorMotivo.set('Motivo de rechazo es obligatorio');
    } else {
      this.errorMotivo.set('');
    }
  }

  aprobar() {
    this.rechazando.set(false);
    this.errorMotivo.set('');
    this.motivoRechazo.set('');
    this.enviarDecision('Aprobada');
  }

  rechazar() {
    this.rechazando.set(true);
    if (!this.motivoRechazo()) {
      this.errorMotivo.set('Motivo de rechazo es obligatorio');
      return;
    }
    this.enviarDecision('Rechazada', this.motivoRechazo());
  }

  async enviarDecision(estado: string, motivo?: string) {
    this.mensajeEstado.set('');
    this.errorMotivo.set('');

    // Simular llamada a API o lógica para registrar la decisión
    // Como no hay endpoint público para aprobación, solo mostrar confirmación

    // Validar motivo si es rechazo
    if (estado === 'Rechazada' && (!motivo || motivo.trim() === '')) {
      this.errorMotivo.set('Motivo de rechazo es obligatorio');
      return;
    }

    // Mostrar estado
    this.estado.set(estado);
    if (estado === 'Aprobada') {
      this.mensajeEstado.set('Solicitud aprobada y notificación enviada al administrador de Active Directory.');
    } else {
      this.mensajeEstado.set(`Solicitud rechazada con motivo: ${motivo}`);
    }
  }

  onSubmit(event: Event) {
    event.preventDefault();
    if (this.rechazando()) {
      this.rechazar();
    } else {
      this.aprobar();
    }
  }
}