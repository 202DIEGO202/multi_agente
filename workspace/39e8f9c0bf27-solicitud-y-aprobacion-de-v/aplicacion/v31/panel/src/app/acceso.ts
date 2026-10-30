import { Component, DestroyRef, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AdminApi } from './admin-api';

@Component({
  selector: 'app-acceso', standalone: true, imports: [FormsModule],
  template: `
    <section class="card">
      <h1>Acceso</h1>
      <p>Acceso exclusivo para operadores autorizados. El token se conserva únicamente durante esta sesión del navegador.</p>
      @if (api.accessMessage()) { <p role="alert" class="alert">{{ api.accessMessage() }}</p> }
      @if (error()) { <p role="alert" class="alert">{{ error() }}</p> }
      <form (ngSubmit)="entrar()">
        <label for="admin-token">Token de administración</label>
        <input id="admin-token" name="token" type="password" autocomplete="off" required [ngModel]="token()" (ngModelChange)="token.set($event)" [disabled]="busy()">
        <button type="submit" [disabled]="busy() || !token().trim()">{{ busy() ? 'Comprobando acceso…' : 'Acceder' }}</button>
      </form>
      @if (api.authenticated()) { <button type="button" (click)="api.logout()">Cerrar sesión</button> }
    </section>
  `
})
export class AccesoComponent {
  readonly api = inject(AdminApi);
  private readonly router = inject(Router);
  private readonly abort = new AbortController();
  readonly token = signal('');
  readonly busy = signal(false);
  readonly error = signal('');
  constructor() { inject(DestroyRef).onDestroy(() => { this.abort.abort(); this.token.set(''); }); }
  async entrar() {
    if (this.busy() || !this.token().trim()) return;
    this.busy.set(true); this.error.set('');
    try {
      this.api.saveToken(this.token());
      this.token.set('');
      await this.api.request('solicitudes?pendientes=true&limite=1&offset=0', 'GET', undefined, this.abort.signal);
      await this.router.navigateByUrl('/revision-jefe');
    } catch (error) {
      if (!this.abort.signal.aborted) {
        this.error.set(error instanceof Error ? error.message : 'No se pudo verificar el acceso.');
        if (this.api.authenticated()) this.api.logout('No se pudo verificar el acceso administrativo. Vuelva a intentar.');
      }
    } finally { this.busy.set(false); }
  }
}