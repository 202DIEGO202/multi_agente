import { Injectable, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

export class AdminError extends Error {
  constructor(public readonly status: number, message: string) { super(message); }
}

@Injectable({ providedIn: 'root' })
export class AdminSession {
  private readonly router = inject(Router);
  private readonly key = 'panel.admin.token';
  private generation = 0;
  readonly authenticated = signal(!!sessionStorage.getItem(this.key));
  readonly message = signal('');

  hasToken(): boolean { return !!sessionStorage.getItem(this.key); }

  start(token: string): void {
    sessionStorage.setItem(this.key, token);
    this.generation++;
    this.authenticated.set(true);
    this.message.set('');
  }

  logout(message = ''): void {
    sessionStorage.removeItem(this.key);
    this.generation++;
    this.authenticated.set(false);
    this.message.set(message);
    void this.router.navigateByUrl('/');
  }

  async request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    // Solo se permiten endpoints del espacio administrativo.
    if (!/^\/api\/admin\/[^/?#]+/.test(path)) {
      throw new AdminError(0, 'Ruta administrativa no válida.');
    }
    const token = sessionStorage.getItem(this.key);
    if (!token) {
      this.logout('Introduzca el Token de administración para acceder.');
      throw new AdminError(401, 'Autenticación administrativa requerida.');
    }
    const generation = this.generation;
    let response: Response;
    try {
      response = await fetch(path, {
        method,
        headers: {
          Authorization: `Bearer ${token}`,
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' })
        },
        body: body === undefined ? undefined : JSON.stringify(body),
        cache: 'no-store',
        credentials: 'omit'
      });
    } catch {
      throw new AdminError(0, 'No se pudo conectar con la API. Intente nuevamente.');
    }
    if (generation !== this.generation) throw new AdminError(0, 'La sesión cambió.');
    if (response.status === 401) {
      this.logout('El Token de administración es inválido o ha caducado. Vuelva a acceder.');
      throw new AdminError(401, 'Autenticación administrativa requerida.');
    }
    const data: unknown = await response.json().catch(() => null);
    if (generation !== this.generation) throw new AdminError(0, 'La sesión cambió.');
    if (!response.ok) {
      let message = response.status === 403 ? 'No tiene autorización para esta operación.' : `La operación no se pudo completar (${response.status}).`;
      if (data && typeof data === 'object' && 'detail' in data) {
        const detail = (data as { detail: unknown }).detail;
        if (typeof detail === 'string') message = detail;
        else if (Array.isArray(detail)) {
          message = detail.map(item => typeof item?.msg === 'string' ? item.msg : 'Entrada inválida').join('. ');
        }
      }
      throw new AdminError(response.status, message);
    }
    return data as T;
  }
}