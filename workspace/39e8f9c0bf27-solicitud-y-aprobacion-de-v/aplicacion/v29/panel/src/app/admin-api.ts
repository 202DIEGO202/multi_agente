import { Injectable, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

export interface Identidad {
  id: number;
  identidad_externa: string;
  nombre: string;
  roles: string[];
}

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) { super(message); }
}

export function mensajeError(error: unknown): string {
  return error instanceof Error ? error.message : 'No fue posible completar la operación.';
}

// Usa las rutas del contrato y sustituye sus identificadores antes de llamar.
function endpointPanel(ruta: string): string {
  const separador = ruta.indexOf('?');
  const recurso = separador < 0 ? ruta : ruta.slice(0, separador);
  const query = separador < 0 ? '' : ruta.slice(separador);
  const endpoints: Record<string, string> = {
    identidad: '/api/admin/identidad',
    flujos: '/api/admin/flujos',
    'tipos-ausencia': '/api/admin/tipos-ausencia',
    'revisiones/pendientes': '/api/admin/revisiones/pendientes'
  };
  if (Object.prototype.hasOwnProperty.call(endpoints, recurso)) {
    return endpoints[recurso] + query;
  }
  const tipo = /^tipos-ausencia\/([1-9]\d*)$/.exec(recurso);
  if (tipo) {
    return '/api/admin/tipos-ausencia/{tipo_id}'.replace('{tipo_id}', tipo[1]) + query;
  }
  const solicitud = /^solicitudes\/([1-9]\d*)$/.exec(recurso);
  if (solicitud) {
    return '/api/admin/solicitudes/{solicitud_id}'.replace('{solicitud_id}', solicitud[1]) + query;
  }
  const decision = /^revisiones\/([1-9]\d*)\/decision$/.exec(recurso);
  if (decision) {
    return '/api/admin/revisiones/{revision_id}/decision'.replace('{revision_id}', decision[1]) + query;
  }
  throw new ApiError(0, 'El recurso solicitado no está configurado en este panel.');
}

@Injectable({ providedIn: 'root' })
export class AdminApi {
  private readonly router = inject(Router);
  private readonly clave = 'panel.admin.token';
  readonly autenticado = signal(this.tieneToken());
  readonly identidad = signal<Identidad | null>(null);
  readonly mensajeAcceso = signal('');

  tieneToken(): boolean { return !!sessionStorage.getItem(this.clave); }

  guardarToken(valor: string): void {
    sessionStorage.setItem(this.clave, valor);
    this.identidad.set(null);
    this.autenticado.set(true);
    this.mensajeAcceso.set('');
  }

  cerrarSesion(mensaje = 'Sesión cerrada. Introduce tu token para volver a acceder.'): void {
    sessionStorage.removeItem(this.clave);
    this.identidad.set(null);
    this.autenticado.set(false);
    this.mensajeAcceso.set(mensaje);
    void this.router.navigateByUrl('/');
  }

  async cargarIdentidad(): Promise<Identidad> {
    const identidad = await this.request<Identidad>('identidad');
    this.identidad.set(identidad);
    return identidad;
  }

  async request<T>(ruta: string, metodo = 'GET', cuerpo?: unknown): Promise<T> {
    const token = sessionStorage.getItem(this.clave);
    if (!token) {
      this.cerrarSesion('Se requiere un token de administración.');
      throw new ApiError(401, 'Se requiere un token de administración.');
    }
    const endpoint = endpointPanel(ruta);
    let respuesta: Response;
    try {
      respuesta = await fetch(endpoint, {
        method: metodo,
        headers: {
          Authorization: `Bearer ${token}`,
          ...(cuerpo === undefined ? {} : { 'Content-Type': 'application/json' })
        },
        body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
        cache: 'no-store',
        credentials: 'omit'
      });
    } catch {
      throw new ApiError(0, 'No se pudo conectar con la API. Comprueba la conexión e inténtalo de nuevo.');
    }
    if (sessionStorage.getItem(this.clave) !== token) {
      throw new ApiError(401, 'La sesión ha cambiado. Vuelve a acceder.');
    }
    if (respuesta.status === 401) {
      const mensaje = 'Token de administración inválido o sesión no autorizada. Vuelve a acceder.';
      this.cerrarSesion(mensaje);
      throw new ApiError(401, mensaje);
    }
    const datos: unknown = await respuesta.json().catch(() => null);
    if (!respuesta.ok) {
      let mensaje = respuesta.status === 403 ? 'No tienes permisos para esta operación.' :
        respuesta.status === 409 ? 'Los datos cambiaron. Vuelve a consultarlos antes de guardar.' :
        respuesta.status === 422 ? 'Revisa los campos y las reglas de la operación.' :
        respuesta.status === 404 ? 'El recurso ya no está disponible.' : 'El servicio no está disponible. Inténtalo de nuevo.';
      if (datos && typeof datos === 'object' && 'detail' in datos) {
        const detalle = (datos as { detail: unknown }).detail;
        if (typeof detalle === 'string') mensaje = detalle;
        else if (Array.isArray(detalle)) {
          mensaje = detalle.map((item: { loc?: unknown[]; msg?: string }) =>
            `${item.loc?.filter(x => x !== 'body').join('.') || 'Datos'}: ${item.msg || 'Valor inválido'}`
          ).join('\n');
        }
      }
      throw new ApiError(respuesta.status, mensaje);
    }
    return datos as T;
  }
}