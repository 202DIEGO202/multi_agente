import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { FormsModule, NgForm } from '@angular/forms';

@Component({
  selector: 'app-solicitud-detalle',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule],
  template: `
    <h2>Detalle de solicitud #{{solicitud?.id}}</h2>
    <div *ngIf="cargando">Cargando...</div>
    <div *ngIf="error" class="error">{{error}}</div>
    <div *ngIf="solicitud" class="card">
      <h3>Datos del solicitante</h3>
      <p><strong>Cédula:</strong> {{solicitud.cedula}}</p>
      <p><strong>Nombres:</strong> {{solicitud.nombres}}</p>
      <p><strong>Área:</strong> {{solicitud.area}}</p>
      <p><strong>Cargo:</strong> {{solicitud.cargo}}</p>
      <p><strong>Fecha de nacimiento:</strong> {{solicitud.fecha_nacimiento}}</p>
      <p><strong>Edad:</strong> {{edad}}</p>
      <p><strong>Nivel de estudios:</strong> {{solicitud.nivel_estudios}}</p>
      <p><strong>Estado:</strong> <span [class.badge]="true" [class.success]="solicitud.estado==='Aprobada'" [class.danger]="solicitud.estado==='Rechazada'">{{solicitud.estado}}</span></p>
      <p *ngIf="solicitud.motivo_rechazo"><strong>Motivo rechazo:</strong> {{solicitud.motivo_rechazo}}</p>

      <div *ngIf="solicitud.estado === 'Pendiente'">
        <form #form="ngForm" (ngSubmit)="actualizarEstado(form)" novalidate>
          <label class="field">
            <input type="radio" name="aprobado" [(ngModel)]="aprobado" [value]="true" required /> Aprobar
          </label>
          <label class="field">
            <input type="radio" name="aprobado" [(ngModel)]="aprobado" [value]="false" required /> Rechazar
          </label>
          <label class="field" *ngIf="aprobado === false">
            Motivo de rechazo
            <input name="motivo_rechazo" [(ngModel)]="motivo_rechazo" required #motivoRef="ngModel" />
          </label>
          <div *ngIf="aprobado === false && motivoRef.invalid && motivoRef.touched" class="error">Motivo es obligatorio si rechaza.</div>

          <div class="actions">
            <button type="submit" [disabled]="form.invalid || cargando">Enviar decisión</button>
            <button type="button" class="secondary" (click)="volver()" [disabled]="cargando">Volver</button>
          </div>
        </form>
      </div>
      <div *ngIf="solicitud.estado !== 'Pendiente'">
        <button (click)="volver()">Volver</button>
      </div>

      <div *ngIf="mensaje" [class.success]="exito" [class.error]="!exito" class="alert">{{mensaje}}</div>
    </div>
  `
})
export class SolicitudDetalleComponent implements OnInit {
  solicitud: any = null;
  edad = 0;
  aprobado: boolean | null = null;
  motivo_rechazo = '';
  mensaje = '';
  exito = false;
  error = '';
  cargando = false;

  private route = inject(ActivatedRoute);
  private router = inject(Router);

  ngOnInit() {
    const id = Number(this.route.snapshot.paramMap.get('id'));
    if (isNaN(id) || id <= 0) {
      this.error = 'ID de solicitud inválido.';
      return;
    }
    this.cargarSolicitud(id);
  }

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

  async cargarSolicitud(id: number) {
    this.cargando = true;
    this.error = '';
    try {
      const res = await fetch(`/api/solicitudes/${id}`);
      if (!res.ok) {
        this.error = 'Error al cargar la solicitud.';
        this.cargando = false;
        return;
      }
      this.solicitud = await res.json();
      this.edad = this.calcularEdad(this.solicitud.fecha_nacimiento);
    } catch {
      this.error = 'Error de conexión al cargar la solicitud.';
    } finally {
      this.cargando = false;
    }
  }

  async actualizarEstado(form: NgForm) {
    if (!form.valid || this.aprobado === null) return;
    if (this.aprobado === false && !this.motivo_rechazo.trim()) return;

    this.cargando = true;
    this.mensaje = '';
    this.exito = false;

    const body = {
      aprobado: this.aprobado,
      motivo_rechazo: this.aprobado ? '' : this.motivo_rechazo.trim()
    };

    try {
      const res = await fetch(`/api/solicitudes/${this.solicitud.id}/estado`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (!res.ok) {
        const text = await res.text();
        this.mensaje = `Error al actualizar estado: ${text}`;
        return;
      }
      this.mensaje = 'Estado de solicitud actualizado correctamente.';
      this.exito = true;
      // Refrescar datos
      await this.cargarSolicitud(this.solicitud.id);
    } catch {
      this.mensaje = 'Error de conexión al actualizar estado.';
    } finally {
      this.cargando = false;
    }
  }

  volver() {
    this.router.navigate(['/solicitudes']);
  }
}