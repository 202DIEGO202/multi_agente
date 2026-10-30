import { CommonModule } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

interface TipoAusencia {
  id: number;
  nombre: string;
}

interface SolicitudResumen {
  solicitud: string;
  estado: string;
  ultimoCambio: string;
}

@Component({
  selector: 'app-solicitudes-ausencia',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <section>
      <h1>Solicitudes de ausencia</h1>

      <div class="card">
        <h2>Solicitante</h2>
        <div>Nombre: Laura Gómez</div>
        <div>Documento: 1023456789</div>
        <div>Área: Operaciones</div>
        <div>Cargo: Analista</div>
      </div>

      <form (ngSubmit)="enviar()">
        <label class="field">Tipo de ausencia
          <select [(ngModel)]="tipoAusenciaId" name="tipoAusenciaId">
            <option value="">Seleccione</option>
            <option *ngFor="let tipo of tipos()" [ngValue]="tipo.id">{{ tipo.nombre }}</option>
          </select>
        </label>
        @if (errores().tipoAusenciaId) { <div class="error">{{ errores().tipoAusenciaId }}</div> }

        <label class="field">Fecha de inicio
          <input type="date" [(ngModel)]="fechaInicio" name="fechaInicio" />
        </label>
        @if (errores().fechaInicio) { <div class="error">{{ errores().fechaInicio }}</div> }

        <label class="field">Fecha de fin
          <input type="date" [(ngModel)]="fechaFin" name="fechaFin" />
        </label>
        @if (errores().fechaFin) { <div class="error">{{ errores().fechaFin }}</div> }

        <label class="field">Hora de inicio (si aplica)
          <input type="time" [(ngModel)]="horaInicio" name="horaInicio" />
        </label>

        <label class="field">Hora de fin (si aplica)
          <input type="time" [(ngModel)]="horaFin" name="horaFin" />
        </label>

        <label class="field">Motivo u observación del permiso (si aplica al tipo seleccionado)
          <input [(ngModel)]="motivo" name="motivo" />
        </label>
        @if (errores().motivo) { <div class="error">{{ errores().motivo }}</div> }

        <button type="submit">Enviar solicitud</button>
      </form>

      @if (mensaje()) { <div class="success">{{ mensaje() }}</div> }
      @if (errorApi()) { <div class="alert">{{ errorApi() }}</div> }

      <div class="card">
        <h2>Historial de solicitudes</h2>
        <div *ngFor="let s of historial()">
          <div>Solicitud: {{ s.solicitud }}</div>
          <div>Estado: {{ s.estado }}</div>
          <div>Último cambio: {{ s.ultimoCambio }}</div>
        </div>
      </div>

      <a routerLink="/detalle">Consultar detalle e historial</a>
    </section>
  `,
})
export class SolicitudesAusenciaComponent implements OnInit {
  tipos = signal<TipoAusencia[]>([]);
  historial = signal<SolicitudResumen[]>([
    { solicitud: 'Vacaciones del 12/07 al 19/07', estado: 'En revisión', ultimoCambio: 'Aprobador asignado' },
    { solicitud: 'Permiso personal 03/08', estado: 'Aprobado', ultimoCambio: 'Cerrada' },
  ]);
  errores = signal<{ [k: string]: string }>({});
  mensaje = signal('');
  errorApi = signal('');
  tipoAusenciaId = '';
  fechaInicio = '';
  fechaFin = '';
  horaInicio = '';
  horaFin = '';
  motivo = '';

  ngOnInit(): void {
    fetch('/api/tipos-ausencia').then(r => r.ok ? r.json() : []).then(data => this.tipos.set(data));
  }

  private validar(): boolean {
    const e: Record<string, string> = {};
    if (!this.tipoAusenciaId) e['tipoAusenciaId'] = 'El tipo de ausencia es obligatorio.';
    if (!this.fechaInicio) e['fechaInicio'] = 'La fecha de inicio es obligatoria.';
    if (!this.fechaFin) e['fechaFin'] = 'La fecha de fin es obligatoria.';
    if (this.fechaInicio && this.fechaFin && this.fechaFin < this.fechaInicio) e['fechaFin'] = 'La fecha de fin debe ser igual o posterior a la de inicio.';
    this.errores.set(e);
    return Object.keys(e).length === 0;
  }

  enviar(): void {
    this.mensaje.set('');
    this.errorApi.set('');
    if (!this.validar()) return;
    fetch('/api/solicitudes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        solicitante_nombre: 'Laura Gómez',
        solicitante_documento: '1023456789',
        area: 'Operaciones',
        cargo: 'Analista',
        tipo_ausencia_id: Number(this.tipoAusenciaId),
        fecha_inicio: this.fechaInicio,
        fecha_fin: this.fechaFin,
        hora_inicio: this.horaInicio || null,
        hora_fin: this.horaFin || null,
        motivo_observacion: this.motivo || null,
        creado_por: 'Laura Gómez',
        creador_rol: 'EMPLEADO',
      }),
    }).then(async r => {
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { this.errorApi.set(data.detail ?? 'No fue posible enviar la solicitud.'); return; }
      this.mensaje.set(`Solicitud creada con ID ${data.id}.`);
    });
  }
}