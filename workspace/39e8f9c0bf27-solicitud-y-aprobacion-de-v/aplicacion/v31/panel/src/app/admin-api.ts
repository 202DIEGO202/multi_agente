import { Injectable, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

export interface SolicitudLista {
  id: number;
  version: number;
  solicitante: string;
  area: string;
  tipo_ausencia: string;
  fecha_inicio: string;
  fecha_fin: string;
  hora_inicio: string | null;
  hora_fin: string | null;
  motivo: string | null;
  estado_codigo: string;
}
export interface Revision {
  id: number;
  orden: number;
  rol_codigo: string;
  estado: string;
  validada_en: string | null;
}
export interface SolicitudDetalle extends Omit<SolicitudLista, 'solicitante' | 'tipo_ausencia' | 'area'> {
  solicitante: { id: number; nombre: string; area: string; cargo: string };
  revisiones: Revision[];
}
export interface Evento {
  id: number;
  version?: number;
  creado_en?: string;
  actor_id?: number;
  accion?: string;
  texto?: string;
  estado_anterior?: string;
  estado_nuevo?: string;
}
export interface Historial {
  historial: Evento[];
  observaciones: Evento[];
  decisiones: Evento[];
}
export interface Aviso { id: number; solicitud_id: number; creado_en: string; prioridad: string; }
export interface TipoAusencia {
  id: number;
  nombre: string;
  estado: 'ACTIVO' | 'INACTIVO';
  requiere_motivo: boolean;
  permite_horas: boolean;
  flujo_codigo: string;
  flujo_nombre: string;
}
export interface Flujo { codigo: string; nombre: string; pasos: { orden: number; rol_codigo: string }[]; }

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) { super(message); }
}

@Injectable({ providedIn: 'root' })
export class AdminApi {
  private readonly router = inject(Router);
  private readonly storageKey = 'panel.admin.token';
  readonly authenticated = signal(!!this.token());
  readonly accessMessage = signal('');

  private token(): string {
    try { return sessionStorage.getItem(this.storageKey) ?? ''; }
    catch { return ''; }
  }

  guard() {
    if (this.token()) { this.authenticated.set(true); return true; }
    this.authenticated.set(false);
    this.accessMessage.set('Introduzca el Token de administración para acceder.');
    return this.router.createUrlTree(['/']);
  }

  saveToken(value: string) {
    sessionStorage.setItem(this.storageKey, value.trim());
    this.authenticated.set(!!value.trim());
    this.accessMessage.set('');
  }

  logout(message = 'Sesión cerrada. Introduzca el Token de administración para acceder.') {
    try { sessionStorage.removeItem(this.storageKey); } catch { /* Almacenamiento no disponible. */ }
    this.authenticated.set(false);
    this.accessMessage.set(message);
    void this.router.navigateByUrl('/');
  }

  private endpoint(path: string, method: string): URL {
    // Solo se admiten recursos del contrato administrativo.
    const base = new URL('/api/admin/', window.location.origin);
    const url = new URL(path, base);
    const resources: Record<string, RegExp> = {
      GET: /^\/api\/admin\/(solicitudes(?:\/[1-9]\d*(?:\/historial)?)?|tipos-ausencia(?:\/[1-9]\d*)?|flujos|notificaciones)$/,
      POST: /^\/api\/admin\/(solicitudes\/[1-9]\d*\/decisiones|tipos-ausencia)$/,
      PUT: /^\/api\/admin\/tipos-ausencia\/[1-9]\d*(?:\/flujo)?$/,
      DELETE: /^\/api\/admin\/tipos-ausencia\/[1-9]\d*$/
    };
    if (url.origin !== base.origin || url.username || url.password || url.hash || !resources[method]?.test(url.pathname)) {
      throw new ApiError(0, 'El recurso solicitado no pertenece al contrato de la API administrativa.');
    }
    return url;
  }

  async request<T>(path: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
    const token = this.token();
    if (!token) {
      this.logout('Se requiere un Token de administración para acceder.');
      throw new ApiError(401, 'Se requiere autenticación administrativa.');
    }
    const url = this.endpoint(path, method);
    let response: Response;
    try {
      response = await fetch(url, {
        method,
        headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
        body: body === undefined ? undefined : JSON.stringify(body),
        cache: 'no-store',
        signal
      });
    } catch (error) {
      if (signal?.aborted) throw error;
      throw new ApiError(0, 'No se pudo conectar con la API. Vuelva a intentar.');
    }
    if (response.status === 401) {
      this.logout('El Token de administración es inválido o ha expirado. Vuelva a introducirlo.');
      throw new ApiError(401, this.accessMessage());
    }
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = data?.detail;
      const message = typeof detail === 'string' ? detail : Array.isArray(detail)
        ? detail.map((item: { msg?: string }) => item.msg ?? 'Dato inválido').join('; ')
        : response.status === 403 ? 'No tiene autorización para esta operación.' : 'No se pudo completar la operación.';
      throw new ApiError(response.status, message);
    }
    if (!this.authenticated() || this.token() !== token) throw new ApiError(401, 'La sesión cambió.');
    return data as T;
  }
}