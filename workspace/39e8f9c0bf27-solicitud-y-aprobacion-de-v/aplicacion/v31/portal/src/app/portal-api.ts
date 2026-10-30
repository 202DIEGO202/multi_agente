import { Injectable, inject } from '@angular/core';
import { Router } from '@angular/router';

export interface Empleado {
  id: number;
  nombre: string;
  documento: string;
  correo: string;
  turno: string | null;
  area: string;
  cargo: string;
}
// Solo los campos autorizados del catálogo del portal.
export interface TipoAusencia {
  id: number;
  nombre: string;
  requiere_motivo: boolean;
  permite_horas: boolean;
}
export interface CrearSolicitud {
  tipo_ausencia_id: number;
  fecha_inicio: string;
  fecha_fin: string;
  hora_inicio: string | null;
  hora_fin: string | null;
  motivo: string | null;
  origen: 'PORTAL' | 'FORMATO_OFICIAL';
  referencia_formato?: string | null;
}
export interface Solicitud {
  id: number;
  tipo_ausencia_id: number;
  tipo_ausencia?: string | null;
  fecha_inicio: string;
  fecha_fin: string;
  hora_inicio: string | null;
  hora_fin: string | null;
  motivo: string | null;
  estado_codigo: string;
  version: number;
  creado_en: string;
  actualizado_en?: string;
}
export interface Notificacion {
  id: number;
  solicitud_id: number;
  tipo: string;
  prioridad: string;
  creado_en: string;
  leida_en: string | null;
  estado_anterior: string | null;
  estado_nuevo: string | null;
}
export interface EventoHistorial {
  version: number;
  estado_anterior: string | null;
  estado_nuevo: string;
  operacion: string;
  creado_en: string;
}
export interface Observacion {
  tipo: string;
  texto: string;
  creado_en: string;
}
export interface Decision {
  accion: string;
  version_resultante: number;
  creado_en: string;
}
export interface Historial {
  historial: EventoHistorial[];
  observaciones: Observacion[];
  decisiones: Decision[];
}
interface TokenRespuesta {
  token: string;
  tipo: string;
  expira_en: number;
}

@Injectable({ providedIn: 'root' })
export class PortalApi {
  private readonly router = inject(Router);
  private readonly clave = 'portal_token';

  tieneSesion(): boolean {
    return !!sessionStorage.getItem(this.clave);
  }

  cerrarSesion(): void {
    sessionStorage.removeItem(this.clave);
    void this.router.navigate(['/acceso']);
  }

  async acceder(documento: string): Promise<void> {
    sessionStorage.removeItem(this.clave);
    const respuesta = await this.peticion<TokenRespuesta>('/api/acceso', {
      method: 'POST', body: JSON.stringify({ documento: documento.trim() })
    }, false);
    sessionStorage.setItem(this.clave, respuesta.token);
  }

  async peticion<T>(ruta: string, opciones: RequestInit = {}, identidad = true): Promise<T> {
    const headers = new Headers(opciones.headers);
    headers.set('Accept', 'application/json');
    if (opciones.body !== undefined) headers.set('Content-Type', 'application/json');
    if (identidad) {
      const token = sessionStorage.getItem(this.clave);
      if (!token) {
        this.cerrarSesion();
        throw new Error('Se requiere un token Bearer');
      }
      headers.set('Authorization', `Bearer ${token}`);
    }
    let respuesta: Response;
    try {
      respuesta = await fetch(ruta, { ...opciones, headers, cache: 'no-store' });
    } catch {
      throw new Error('No se pudo conectar con el servicio. Vuelva a intentar.');
    }
    const datos: unknown = await respuesta.json().catch(() => null);
    if (!respuesta.ok) {
      if (respuesta.status === 401 && identidad) this.cerrarSesion();
      throw new Error(this.mensaje(datos, respuesta.status));
    }
    return datos as T;
  }

  private mensaje(datos: unknown, estado: number): string {
    if (datos && typeof datos === 'object' && 'detail' in datos) {
      const detalle = (datos as { detail: unknown }).detail;
      if (typeof detalle === 'string') return detalle;
      if (Array.isArray(detalle)) {
        return detalle.map((item: unknown) => {
          if (item && typeof item === 'object' && 'msg' in item) return String((item as { msg: unknown }).msg);
          return 'Datos inválidos';
        }).join('; ');
      }
    }
    return `No se pudo completar la operación (${estado}).`;
  }
}

export function mensajeError(error: unknown): string {
  return error instanceof Error ? error.message : 'No se pudo completar la operación.';
}
export function estadoVisible(estado: string | null | undefined): string {
  return estado ? estado.replaceAll('_', ' ') : '—';
}