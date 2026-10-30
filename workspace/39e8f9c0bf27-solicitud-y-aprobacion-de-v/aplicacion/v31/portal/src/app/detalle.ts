import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { Historial, Notificacion, PortalApi, Solicitud, TipoAusencia, estadoVisible, mensajeError } from './portal-api';

@Component({
  selector: 'app-detalle',
  standalone: true,
  imports: [RouterLink, DatePipe],
  template: `
    <h1>Notificaciones y detalle de solicitud</h1>
    <div class="actions">
      <a routerLink="/">Volver a solicitudes</a>
      <button type="button" class="secondary" (click)="cargar()" [disabled]="cargando()">Actualizar</button>
      <button type="button" class="secondary" (click)="api.cerrarSesion()">Cerrar sesión</button>
    </div>
    @if (cargando()) { <p role="status">Cargando detalle e historial…</p> }
    @if (error()) { <p class="error" role="alert">{{ error() }}</p> }
    @if (solicitud(); as datos) {
      <section class="card">
        <h2>Detalle e historial</h2>
        <p>Solicitud: #{{ datos.id }}</p>
        <p>Tipo de ausencia: {{ nombreTipo() }}</p>
        <p>Fechas: {{ datos.fecha_inicio }} - {{ datos.fecha_fin }}</p>
        <p>Horas: {{ datos.hora_inicio && datos.hora_fin ? datos.hora_inicio + ' - ' + datos.hora_fin : 'No aplica' }}</p>
        <p>Observación: {{ datos.motivo || 'Sin observación' }}</p>
        <p>Estado: <span class="badge">{{ estado(datos.estado_codigo) }}</span></p>
        <p>Versión: {{ datos.version }}</p>
        @if (historial(); as seguimiento) {
          <h3>Historial</h3>
          @if (!seguimiento.historial.length) { <p>No hay cambios de estado disponibles.</p> }
          @if (seguimiento.historial.length) {
            <table>
              <thead><tr><th>Versión</th><th>Estado anterior</th><th>Nuevo estado</th><th>Fecha</th></tr></thead>
              <tbody>
                @for (evento of seguimiento.historial; track evento.version) {
                  <tr><td>{{ evento.version }}</td><td>{{ estado(evento.estado_anterior) }}</td><td>{{ estado(evento.estado_nuevo) }}</td><td>{{ evento.creado_en | date:'dd/MM/yyyy HH:mm' }}</td></tr>
                }
              </tbody>
            </table>
          }
          <h3>Observaciones</h3>
          @if (!seguimiento.observaciones.length) { <p>No hay observaciones de revisión.</p> }
          @for (observacion of seguimiento.observaciones; track $index) {
            <article class="card">
              <p>{{ estado(observacion.tipo) }} · {{ observacion.creado_en | date:'dd/MM/yyyy HH:mm' }}</p>
              <p>{{ observacion.texto }}</p>
            </article>
          }
          <h3>Decisiones</h3>
          @if (!seguimiento.decisiones.length) { <p>No hay decisiones registradas.</p> }
          @for (decision of seguimiento.decisiones; track decision.version_resultante) {
            <p>{{ estado(decision.accion) }} · Versión {{ decision.version_resultante }} · {{ decision.creado_en | date:'dd/MM/yyyy HH:mm' }}</p>
          }
        }
      </section>
      <section class="card">
        <h2>Notificación de cambio de estado</h2>
        @if (!avisos().length) { <p>No hay avisos disponibles para esta solicitud en la página consultada.</p> }
        @if (errorAviso()) { <p class="error" role="alert">{{ errorAviso() }}</p> }
        @for (aviso of avisos(); track aviso.id) {
          <article class="card">
            <p>Solicitud: #{{ aviso.solicitud_id }}</p>
            <p>Estado anterior: {{ estado(aviso.estado_anterior) }}</p>
            <p>Nuevo estado: {{ estado(aviso.estado_nuevo) }}</p>
            <p>Fecha del aviso: {{ aviso.creado_en | date:'dd/MM/yyyy HH:mm' }}</p>
            @if (aviso.leida_en) {
              <p class="badge">Leída · {{ aviso.leida_en | date:'dd/MM/yyyy HH:mm' }}</p>
            } @else {
              <button type="button" (click)="marcarLeida(aviso)" [disabled]="leyendo() !== null">Marcar como leída</button>
            }
          </article>
        }
        <div class="actions">
          <button type="button" class="secondary" (click)="paginaAvisos(-1)" [disabled]="offset() === 0 || cargando()">Avisos anteriores</button>
          <span>Página {{ offset() / limite + 1 }} de avisos propios</span>
          <button type="button" class="secondary" (click)="paginaAvisos(1)" [disabled]="cantidadAvisos() < limite || cargando()">Más avisos</button>
        </div>
      </section>
      <section class="card">
        <h2>Notificación de pendientes de revisión</h2>
        <p>Los avisos de solicitudes pendientes se envían al aprobador correspondiente. Este portal muestra únicamente sus propios avisos de cambio de estado; no permite consultar la bandeja de aprobadores.</p>
      </section>
    }
  `
})
export class DetalleComponent implements OnInit, OnDestroy {
  readonly api = inject(PortalApi);
  private readonly route = inject(ActivatedRoute);
  readonly solicitud = signal<Solicitud | null>(null);
  readonly historial = signal<Historial | null>(null);
  readonly nombreTipo = signal('');
  readonly avisos = signal<Notificacion[]>([]);
  readonly cantidadAvisos = signal(0);
  readonly offset = signal(0);
  readonly limite = 50;
  readonly cargando = signal(false);
  readonly leyendo = signal<number | null>(null);
  readonly error = signal('');
  readonly errorAviso = signal('');
  readonly estado = estadoVisible;
  private id = 0;
  private generacion = 0;
  private subscripcion?: Subscription;
  private temporizador?: ReturnType<typeof setInterval>;

  ngOnInit(): void {
    this.subscripcion = this.route.paramMap.subscribe(parametros => {
      this.generacion++;
      this.id = Number(parametros.get('id'));
      this.offset.set(0);
      this.solicitud.set(null);
      this.historial.set(null);
      this.avisos.set([]);
      if (!Number.isSafeInteger(this.id) || this.id <= 0) {
        this.cargando.set(false);
        this.error.set('Solicitud inexistente');
        return;
      }
      void this.cargar();
    });
    this.temporizador = setInterval(() => {
      if (this.solicitud() && !this.cargando() && this.leyendo() === null) void this.cargar();
    }, 30000);
  }

  ngOnDestroy(): void {
    this.generacion++;
    this.subscripcion?.unsubscribe();
    if (this.temporizador) clearInterval(this.temporizador);
  }

  async cargar(): Promise<void> {
    if (!Number.isSafeInteger(this.id) || this.id <= 0) return;
    const generacion = ++this.generacion;
    const id = this.id;
    this.cargando.set(true);
    this.error.set('');
    try {
      const [solicitud, historial, tipos, avisos] = await Promise.all([
        this.api.peticion<Solicitud>(`/api/portal/solicitudes/${id}`),
        this.api.peticion<Historial>(`/api/portal/solicitudes/${id}/historial`),
        this.api.peticion<TipoAusencia[]>('/api/portal/tipos-ausencia'),
        this.api.peticion<Notificacion[]>(`/api/portal/notificaciones?limite=${this.limite}&offset=${this.offset()}`)
      ]);
      if (generacion !== this.generacion) return;
      this.solicitud.set(solicitud);
      this.historial.set(historial);
      this.nombreTipo.set(solicitud.tipo_ausencia || tipos.find(tipo => tipo.id === solicitud.tipo_ausencia_id)?.nombre || `Tipo #${solicitud.tipo_ausencia_id}`);
      this.cantidadAvisos.set(avisos.length);
      this.avisos.set(avisos.filter(aviso => aviso.solicitud_id === id));
    } catch (error) {
      if (generacion !== this.generacion) return;
      this.solicitud.set(null);
      this.historial.set(null);
      this.avisos.set([]);
      this.error.set(mensajeError(error));
    } finally {
      if (generacion === this.generacion) this.cargando.set(false);
    }
  }

  paginaAvisos(direccion: number): void {
    if (this.cargando()) return;
    this.offset.update(valor => Math.max(0, valor + direccion * this.limite));
    void this.cargar();
  }

  async marcarLeida(aviso: Notificacion): Promise<void> {
    if (this.leyendo() !== null) return;
    const idSolicitud = this.id;
    this.leyendo.set(aviso.id);
    this.errorAviso.set('');
    try {
      const respuesta = await this.api.peticion<{ id: number; leida_en: string }>(`/api/portal/notificaciones/${aviso.id}/leida`, { method: 'PATCH' });
      if (idSolicitud === this.id) {
        this.avisos.update(avisos => avisos.map(item => item.id === respuesta.id ? { ...item, leida_en: respuesta.leida_en } : item));
      }
    } catch (error) {
      if (idSolicitud === this.id) this.errorAviso.set(mensajeError(error));
    } finally {
      this.leyendo.set(null);
    }
  }
}