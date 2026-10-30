import { Injectable, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

export interface Page<T> { items: T[]; limite: number; desplazamiento: number; }
export interface Revision { id: number; orden: number; estado: string; rol_codigo: string; aprobador_id: number; requiere_validacion?: boolean; }
export interface Solicitud {
  id: number; solicitante_id: number; tipo_ausencia_id: number; version: number; estado_codigo: string;
  fecha_inicio: string; fecha_fin: string; hora_inicio?: string; hora_fin?: string; motivo?: string;
  tipo_ausencia_nombre?: string; revisiones?: Revision[];
  solicitante?: { id: number; nombre: string; area?: string; cargo?: string };
  observaciones?: { id: number; texto: string; creado_en: string; autor_id: number }[];
  aprobaciones?: unknown[];
}
export interface TipoAusencia {
  id: number; nombre: string; estado: string; flujo_codigo: string;
  requiere_motivo: boolean; modalidad_horas: string;
}
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

@Injectable({ providedIn: 'root' })
export class AdminApi {
  private readonly router = inject(Router);
  private readonly tokenKey = 'panel.admin.token';
  private readonly identityKey = 'panel.admin.identity';
  readonly authenticated = signal(!!sessionStorage.getItem(this.tokenKey) && !!sessionStorage.getItem(this.identityKey));
  readonly message = signal('');
  private epoch = 0;

  save(token: string, identity: string): void {
    sessionStorage.setItem(this.tokenKey, token.trim());
    sessionStorage.setItem(this.identityKey, identity.trim());
    this.epoch++;
    this.authenticated.set(true);
    this.message.set('');
  }

  logout(message = 'Sesión cerrada. Introduzca sus credenciales para continuar.'): void {
    sessionStorage.removeItem(this.tokenKey);
    sessionStorage.removeItem(this.identityKey);
    this.epoch++;
    this.authenticated.set(false);
    this.message.set(message);
    void this.router.navigateByUrl('/acceso');
  }

  async request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const token = sessionStorage.getItem(this.tokenKey);
    const identity = sessionStorage.getItem(this.identityKey);
    const epoch = this.epoch;
    if (!token || !identity) {
      this.logout('Debe introducir el Token de administración y el token de identidad para continuar.');
      throw new ApiError(401, this.message());
    }
    let response: Response;
    try {
      response = await fetch('/api/admin/' + path, {
        method, cache: 'no-store', credentials: 'omit',
        headers: { Authorization: `Bearer ${token}`, 'X-Identity-Token': `Bearer ${identity}`, 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body)
      });
    } catch {
      throw new ApiError(0, 'No se pudo conectar con la API. Intente nuevamente.');
    }
    if (epoch !== this.epoch) throw new ApiError(401, 'La sesión cambió.');
    if (response.status === 401) {
      this.logout('Credenciales ausentes, inválidas o caducadas. Vuelva a acceder con ambos tokens válidos.');
      throw new ApiError(401, this.message());
    }
    const payload: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = payload && typeof payload === 'object' && 'detail' in payload ? (payload as { detail: unknown }).detail : null;
      const message = typeof detail === 'string' ? detail : response.status === 422 ? 'Revise los campos y las reglas de la operación.' : response.status === 403 ? 'No tiene autorización para esta operación.' : `La API respondió con un error (${response.status}).`;
      throw new ApiError(response.status, message);
    }
    return payload as T;
  }
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'No se pudo completar la operación.';
}