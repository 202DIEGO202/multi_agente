import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class PortalApi {
  async consultar<T>(ruta: string, cuerpo?: object): Promise<T> {
    const respuesta = await fetch(ruta, {
      method: cuerpo === undefined ? 'GET' : 'POST',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: cuerpo === undefined ? { Accept: 'application/json' } : {
        Accept: 'application/json',
        'Content-Type': 'application/json'
      },
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo)
    });
    const datos: unknown = await respuesta.json().catch(() => null);
    if (!respuesta.ok) {
      const detalle = datos && typeof datos === 'object' && 'detail' in datos
        ? (datos as { detail: unknown }).detail : null;
      if (typeof detalle === 'string') throw new Error(detalle);
      if (Array.isArray(detalle)) {
        const mensajes = detalle.map((item: unknown) => {
          if (item && typeof item === 'object' && 'msg' in item && typeof item.msg === 'string') return item.msg;
          return 'Los datos incumplen las restricciones del dominio';
        });
        throw new Error(mensajes.join('\n'));
      }
      throw new Error(`No se pudo completar la operación (HTTP ${respuesta.status}).`);
    }
    if (datos === null) throw new Error('Respuesta del servidor inválida.');
    return datos as T;
  }

  mensaje(error: unknown): string {
    return error instanceof Error ? error.message : 'No se pudo completar la operación. Intente nuevamente.';
  }
}