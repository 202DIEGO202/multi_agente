import { Injectable, computed, inject, signal } from '@angular/core';
import { AdminApi, ApiError, mensajeError } from './admin-api';

export interface Pendiente {
  solicitud_id: number;
  version_solicitud: number;
  version_revision: number;
  aprobacion_id: number;
  rol_codigo: string;
  requiere_validacion: boolean;
  validada_en: string | null;
  estado_codigo: string;
  solicitante: string;
  area: string | null;
  tipo_ausencia: string;
  fecha_inicio: string;
  fecha_fin: string;
  hora_inicio: string | null;
  hora_fin: string | null;
  motivo: string | null;
}
interface Aprobacion {
  id: number;
  version: number;
  estado: string;
  aprobador_id: number;
  rol_codigo: string;
  requiere_validacion: boolean;
  validada_en: string | null;
}
export interface Detalle {
  id: number;
  version: number;
  estado_codigo: string;
  fecha_inicio: string;
  fecha_fin: string;
  hora_inicio: string | null;
  hora_fin: string | null;
  motivo: string | null;
  aprobaciones: Aprobacion[];
  observaciones: { id: number; contenido: string; accion: string; creado_en: string }[];
}

@Injectable()
export class RevisionStore {
  readonly api = inject(AdminApi);
  readonly pendientes = signal<Pendiente[]>([]);
  readonly seleccion = signal<Pendiente | null>(null);
  readonly detalle = signal<Detalle | null>(null);
  readonly observacion = signal('');
  readonly ocupado = signal(false);
  readonly error = signal('');
  readonly mensaje = signal('');
  readonly offset = signal(0);
  readonly cantidadPagina = signal(0);
  readonly permitido = signal(false);
  private rol = '';
  readonly revision = computed(() => this.detalle()?.aprobaciones.find(a => a.id === this.seleccion()?.aprobacion_id) ?? null);
  readonly puedeDecidir = computed(() => this.permitido() && this.detalle()?.estado_codigo === 'EN_REVISION' &&
    this.revision()?.estado === 'PENDIENTE' && this.revision()?.rol_codigo === this.rol &&
    this.revision()?.aprobador_id === this.api.identidad()?.id);

  async iniciar(rol: string): Promise<void> {
    this.rol = rol;
    this.ocupado.set(true);
    try {
      const actor = await this.api.cargarIdentidad();
      this.permitido.set(actor.roles.includes(rol));
      if (!this.permitido()) throw new Error('No tienes el rol requerido para esta pantalla.');
      await this.cargarLista();
    } catch (error) { this.error.set(mensajeError(error)); }
    finally { this.ocupado.set(false); }
  }

  private async cargarLista(): Promise<void> {
    this.seleccion.set(null);
    this.detalle.set(null);
    this.observacion.set('');
    const lista = await this.api.request<Pendiente[]>(`revisiones/pendientes?limit=50&offset=${this.offset()}`);
    this.cantidadPagina.set(lista.length);
    this.pendientes.set(lista.filter(item => item.rol_codigo === this.rol));
  }

  async recargar(desplazamiento = 0): Promise<void> {
    if (this.ocupado() || !this.permitido()) return;
    this.offset.set(Math.max(0, this.offset() + desplazamiento));
    this.ocupado.set(true);
    this.error.set('');
    this.mensaje.set('');
    this.pendientes.set([]);
    try { await this.cargarLista(); }
    catch (error) { this.error.set(mensajeError(error)); }
    finally { this.ocupado.set(false); }
  }

  async abrir(item: Pendiente): Promise<void> {
    if (this.ocupado()) return;
    this.ocupado.set(true);
    this.error.set('');
    this.mensaje.set('');
    this.seleccion.set(null);
    this.detalle.set(null);
    this.observacion.set('');
    try {
      const detalle = await this.api.request<Detalle>(`solicitudes/${item.solicitud_id}`);
      this.seleccion.set(item);
      this.detalle.set(detalle);
    } catch (error) { this.error.set(mensajeError(error)); }
    finally { this.ocupado.set(false); }
  }

  async decidir(accion: 'APROBAR' | 'RECHAZAR' | 'VALIDAR_APROBAR'): Promise<void> {
    const detalle = this.detalle();
    const revision = this.revision();
    if (this.ocupado() || !this.puedeDecidir() || !detalle || !revision) return;
    const observacion = this.observacion().trim();
    if (accion === 'RECHAZAR' && !observacion) {
      this.error.set('El rechazo requiere una observación con el motivo.');
      return;
    }
    if ((this.rol === 'JEFE_INMEDIATO' && accion === 'VALIDAR_APROBAR') ||
        (this.rol === 'TALENTO_HUMANO' && accion === 'APROBAR')) return;
    this.ocupado.set(true);
    this.error.set('');
    this.mensaje.set('');
    try {
      await this.api.request(`revisiones/${revision.id}/decision`, 'POST', {
        version_solicitud: detalle.version,
        version_revision: revision.version,
        accion,
        ...(observacion ? { observacion } : {})
      });
      this.mensaje.set('Decisión y observaciones registradas correctamente.');
      await this.cargarLista();
    } catch (error) {
      this.error.set(mensajeError(error));
      if (error instanceof ApiError && (error.status === 409 || error.status === 404)) {
        this.seleccion.set(null);
        this.detalle.set(null);
        this.observacion.set('');
        try { await this.cargarLista(); }
        catch (recarga) { this.error.set(mensajeError(error) + ' ' + mensajeError(recarga)); }
      }
    } finally { this.ocupado.set(false); }
  }
}