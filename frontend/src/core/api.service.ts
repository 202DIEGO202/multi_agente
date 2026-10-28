import { Injectable, signal } from '@angular/core';
import { createSSEParser } from './sse.mjs';

@Injectable({providedIn: 'root'})
export class ApiService {
  error = signal('');
  private headers(): Record<string,string> {
    const token = sessionStorage.getItem('fabrica_access') || '';
    return token ? {Authorization: `Bearer ${token}`} : {};
  }
  async request<T = any>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const multipart = body instanceof FormData;
    let response: Response;
    try {
      response = await fetch(`/api${path}`, {method,
        headers: {...this.headers(), ...(body && !multipart ? {'Content-Type':'application/json'} : {})},
        body: body ? (multipart ? body : JSON.stringify(body)) as BodyInit : undefined});
    } catch {
      throw new Error('No hay conexión con el servidor. Comprueba que el backend esté iniciado.');
    }
    if (!response.ok) {
      const value = await response.json().catch(() => ({}));
      throw new Error(typeof value.detail === 'string' ? value.detail : `No se pudo completar la operación (${response.status}).`);
    }
    return response.status === 204 ? undefined as T : response.json();
  }
  async events(path: string, receive: (name: string, data: any) => void, signal: AbortSignal) {
    let cursor = 0, finished = false, failures = 0;
    while (!signal.aborted && !finished) {
      try {
        const response = await fetch(`/api${path}?after=${cursor}`, {headers: this.headers(), signal});
        if (!response.ok || !response.body) throw new Error('No se pudo abrir el monitor de actividad.');
        const decoder = new TextDecoder();
        const parser = createSSEParser(event => {
          if (event.id) cursor = Math.max(cursor, Number(event.id));
          if (event.name === 'fin') finished = true;
          receive(event.name, event.data);
        });
        const reader = response.body.getReader();
        while (!signal.aborted) {
          const {value, done} = await reader.read();
          if (done) break;
          parser(decoder.decode(value, {stream: true}));
          failures = 0;
        }
        parser(decoder.decode());
        if (!finished && !signal.aborted) throw new Error('Conexión interrumpida');
      } catch (error) {
        if (signal.aborted) return;
        if (++failures > 4) throw new Error('Se perdió la conexión. El análisis sigue guardado; puedes abrirlo en Actividad de IA.');
        await new Promise(resolve => setTimeout(resolve, Math.min(1000 * failures, 4000)));
      }
    }
  }
  showError(error: unknown) { this.error.set(error instanceof Error ? error.message : 'Ocurrió un error inesperado.'); }
}
