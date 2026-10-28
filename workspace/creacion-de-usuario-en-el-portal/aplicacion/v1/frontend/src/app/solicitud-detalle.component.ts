import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule, Router } from '@angular/router';

interface Estado {
  id: number;
  nombre: string;
}

interface Solicitud {
  id: number;
  usuario_id: number;
  fecha_envio: string;
  estado: Estado;
  nivel_estudios: string;
  fecha_nacimiento: string;
  cedula: string;
  nombres: string;
  telefono: string;
  correo_electronico: string;
}

interface Solicitante {
  cedula: string;
  nombres: string;
  area: string;
  cargo: string;
  fecha_nacimiento: string;
  edad: number;
  nivel_estudios: string;
}

interface Aprobador {
  id: number;
  nombres: string;
  cargo: string;
}

@Component({
  selector: 'app-solicitud-detalle',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <h2>Detalle de Solicitud #{{solicitud?.id}}</h2>
    <button (click)="volver()" style="margin-bottom:1rem; padding:0.3rem 0.6rem;">Volver</button>

    <section *ngIf="solicitud">
      <h3>Datos del Solicitante</h3>
      <ul>
        <li><strong>Nombres:</strong> {{solicitante?.nombres}}</li>
        <li><strong>Cédula:</strong> {{solicitante?.cedula}}</li>
        <li><strong>Área:</strong> {{solicitante?.area}}</li>
        <li><strong>Cargo:</strong> {{solicitante?.cargo}}</li>
        <li><strong>Fecha de Nacimiento:</strong> {{solicitante?.fecha_nacimiento}}</li>
        <li><strong>Edad:</strong> {{solicitante?.edad}}</li>
        <li><strong>Nivel de Estudios:</strong> {{solicitante?.nivel_estudios}}</li>
      </ul>

      <h3>Datos del Aprobador (Líder de Área)</h3>
      <ul>
        <li><strong>Nombre:</strong> {{aprobador?.nombres}}</li>
        <li><strong>Cargo:</strong> {{aprobador?.cargo}}</li>
      </ul>

      <h3>Estado de la Solicitud</h3>
      <p><strong>Estado:</strong> {{solicitud.estado.nombre}}</p>
      <p><strong>Fecha de Envío:</strong> {{solicitud.fecha_envio | date:'short'}}</p>

      <div *ngIf="solicitud.estado.nombre === 'Pendiente'">
        <button (click)="aprobar()" style="margin-right:1rem; padding:0.5rem 1rem; background:#2e7d32; color:#fff; border:none;">Aprobar</button>
        <button (click)="mostrarRechazo = true" style="padding:0.5rem 1rem; background:#c62828; color:#fff; border:none;">Rechazar</button>
      </div>

      <div *ngIf="mostrarRechazo" style="margin-top:1rem;">
        <label for="motivo">Motivo de Rechazo (obligatorio):</label><br />
        <textarea id="motivo" [(ngModel)]="motivoRechazo" rows="3" cols="40" style="resize:none;"></textarea><br />
        <div *ngIf="errorMotivo" style="color:red; font-size:0.9em;">El motivo es obligatorio para rechazar.</div>
        <button (click)="rechazar()" style="margin-top:0.5rem; padding:0.5rem 1rem; background:#c62828; color:#fff; border:none;">Confirmar Rechazo</button>
        <button (click)="cancelarRechazo()" style="margin-left:0.5rem; padding:0.5rem 1rem;">Cancelar</button>
      </div>

      <div *ngIf="mensajeAccion" style="margin-top:1rem; color:green; font-weight:bold;">{{mensajeAccion}}</div>
      <div *ngIf="errorAccion" style="margin-top:1rem; color:red; font-weight:bold;">{{errorAccion}}</div>
    </section>

    <div *ngIf="errorCarga" style="color:red;">{{errorCarga}}</div>
  `
})
export class SolicitudDetalleComponent implements OnInit {
  solicitud: Solicitud | null = null;
  solicitante: Solicitante | null = null;
  aprobador: Aprobador | null = null;
  errorCarga = '';
  mensajeAccion = '';
  errorAccion = '';
  mostrarRechazo = false;
  motivoRechazo = '';
  errorMotivo = false;

  constructor(private route: ActivatedRoute, private router: Router) {}

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.cargarDetalle(+id);
    } else {
      this.errorCarga = 'ID de solicitud inválido';
    }
  }

  async cargarDetalle(id: number) {
    this.errorCarga = '';
    try {
      const res = await fetch(`/api/solicitudes/${id}`);
      if (!res.ok) {
        this.errorCarga = 'Error al cargar detalle de la solicitud';
        return;
      }
      const data = await res.json();
      this.solicitud = data.solicitud;
      this.solicitante = data.solicitante;
      this.aprobador = data.aprobador;
    } catch {
      this.errorCarga = 'Error de conexión al cargar detalle';
    }
  }

  volver() {
    this.router.navigate(['/solicitudes']);
  }

  async aprobar() {
    this.mensajeAccion = '';
    this.errorAccion = '';
    try {
      const res = await fetch(`/api/solicitudes/${this.solicitud?.id}/estado`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ aprobado: true })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        this.errorAccion = err.mensaje || 'Error al aprobar la solicitud';
        return;
      }
      this.mensajeAccion = 'Solicitud aprobada correctamente.';
      this.cargarDetalle(this.solicitud!.id);
      this.mostrarRechazo = false;
      this.motivoRechazo = '';
    } catch {
      this.errorAccion = 'Error de conexión al aprobar la solicitud';
    }
  }

  cancelarRechazo() {
    this.mostrarRechazo = false;
    this.motivoRechazo = '';
    this.errorMotivo = false;
  }

  async rechazar() {
    this.errorMotivo = false;
    this.mensajeAccion = '';
    this.errorAccion = '';
    if (!this.motivoRechazo.trim()) {
      this.errorMotivo = true;
      return;
    }
    try {
      const res = await fetch(`/api/solicitudes/${this.solicitud?.id}/estado`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ aprobado: false, motivo_rechazo: this.motivoRechazo.trim() })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        this.errorAccion = err.mensaje || 'Error al rechazar la solicitud';
        return;
      }
      this.mensajeAccion = 'Solicitud rechazada correctamente.';
      this.cargarDetalle(this.solicitud!.id);
      this.mostrarRechazo = false;
      this.motivoRechazo = '';
    } catch {
      this.errorAccion = 'Error de conexión al rechazar la solicitud';
    }
  }
}