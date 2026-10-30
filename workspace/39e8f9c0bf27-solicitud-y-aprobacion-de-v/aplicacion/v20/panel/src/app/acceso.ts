import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { AdminError, AdminSession } from './admin-session';

@Component({
  selector: 'app-acceso',
  standalone: true,
  imports: [],
  template: `
    <section class="card">
      <h1>Acceso administrativo</h1>
      <p>Acceso exclusivo para operadores autorizados.</p>
      @if (session.message()) { <p class="alert" role="alert">{{ session.message() }}</p> }
      @if (error()) { <p class="alert" role="alert">{{ error() }}</p> }
      <form (submit)="$event.preventDefault(); acceder(token)">
        <label for="admin-token">Token de administración</label>
        <input #token id="admin-token" type="password" autocomplete="off" required [disabled]="busy()">
        <button class="btn btn-primary" type="submit" [disabled]="busy()">{{ busy() ? 'Verificando acceso…' : 'Acceder' }}</button>
      </form>
      <p>El token se conserva únicamente en sessionStorage durante esta sesión.</p>
      @if (session.authenticated()) {
        <button class="btn" type="button" (click)="continuar()" [disabled]="busy()">Ir a la bandeja</button>
        <button class="btn" type="button" (click)="session.logout()" [disabled]="busy()">Cerrar sesión</button>
      }
    </section>
  `
})
export class Acceso {
  readonly session = inject(AdminSession);
  private readonly router = inject(Router);
  readonly busy = signal(false);
  readonly error = signal('');

  continuar(): void { void this.router.navigateByUrl('/revision'); }

  async acceder(input: HTMLInputElement): Promise<void> {
    if (this.busy()) return;
    if (!input.value.trim()) { this.error.set('Introduzca el Token de administración.'); return; }
    this.session.start(input.value.trim());
    input.value = '';
    this.error.set('');
    this.busy.set(true);
    try {
      await this.session.request<unknown>('/api/admin/revisiones/pendientes?limite=1&offset=0');
      this.continuar();
    } catch (error) {
      if (!(error instanceof AdminError && error.status === 401)) {
        this.session.logout('No se pudo verificar el acceso administrativo.');
        this.error.set(error instanceof Error ? error.message : 'No se pudo acceder.');
      }
    } finally { this.busy.set(false); }
  }
}