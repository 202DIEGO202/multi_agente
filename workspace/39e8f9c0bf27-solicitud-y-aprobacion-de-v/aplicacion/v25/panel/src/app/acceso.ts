import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AdminApi, Page, Solicitud, errorMessage } from './admin-api';

@Component({
  selector: 'app-acceso', standalone: true, imports: [FormsModule],
  template: `
    <section class="card">
      <h1>Acceso administrativo</h1>
      <p>Introduzca las credenciales entregadas por su organización. Solo se guardan durante esta sesión del navegador.</p>
      <p>La API también exige un JWT de identidad del aprobador en X-Identity-Token.</p>
      @if (api.message()) { <p role="alert">{{ api.message() }}</p> }
      @if (error()) { <p role="alert">{{ error() }}</p> }
      @if (api.authenticated()) {
        <p>Hay una sesión administrativa abierta.</p>
        <button type="button" (click)="continuar()">Continuar</button>
        <button type="button" (click)="api.logout()">Cerrar sesión</button>
      }
      <form (ngSubmit)="entrar()">
        <label for="admin-token">Token de administración</label>
        <input id="admin-token" name="adminToken" type="password" autocomplete="off" required [ngModel]="token()" (ngModelChange)="token.set($event)" [disabled]="busy()">
        <label for="identity-token">Token de identidad del aprobador</label>
        <input id="identity-token" name="identityToken" type="password" autocomplete="off" required [ngModel]="identity()" (ngModelChange)="identity.set($event)" [disabled]="busy()">
        <button type="submit" [disabled]="busy() || !token().trim() || !identity().trim()">{{ busy() ? 'Verificando…' : 'Acceder' }}</button>
      </form>
    </section>
  `
})
export class AccesoComponent {
  readonly api = inject(AdminApi);
  private readonly router = inject(Router);
  readonly token = signal('');
  readonly identity = signal('');
  readonly busy = signal(false);
  readonly error = signal('');

  continuar(): void { void this.router.navigateByUrl('/jefe'); }

  async entrar(): Promise<void> {
    if (this.busy() || !this.token().trim() || !this.identity().trim()) return;
    this.busy.set(true);
    this.error.set('');
    this.api.save(this.token(), this.identity());
    this.token.set('');
    this.identity.set('');
    try {
      await this.api.request<Page<Solicitud>>('solicitudes?pendientes=true&limite=1&desplazamiento=0');
      this.continuar();
    } catch (error) {
      const message = errorMessage(error);
      if (this.api.authenticated()) this.api.logout(message);
      this.error.set(message);
    } finally { this.busy.set(false); }
  }
}