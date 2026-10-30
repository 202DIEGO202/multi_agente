import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AdminApi, mensajeError } from './admin-api';

@Component({
  selector: 'app-acceso',
  standalone: true,
  imports: [FormsModule],
  template: `
    <section class="card">
      <h1>Acceso</h1>
      <p>Acceso exclusivo para operadores autorizados. El token se conserva únicamente durante esta sesión del navegador.</p>
      @if (api.mensajeAcceso()) { <p role="alert">{{ api.mensajeAcceso() }}</p> }
      @if (error()) { <p role="alert">{{ error() }}</p> }
      <form (ngSubmit)="entrar()">
        <label for="token-admin">Token de administración</label>
        <input id="token-admin" name="token" type="password" autocomplete="off" required
          [ngModel]="token()" (ngModelChange)="token.set($event)" [disabled]="ocupado()">
        <button type="submit" [disabled]="ocupado() || !token().trim()">{{ ocupado() ? 'Verificando acceso…' : 'Acceder' }}</button>
      </form>
      @if (api.autenticado()) { <button type="button" (click)="api.cerrarSesion()" [disabled]="ocupado()">Cerrar sesión</button> }
    </section>
  `
})
export class AccesoComponent {
  readonly api = inject(AdminApi);
  private readonly router = inject(Router);
  readonly token = signal('');
  readonly error = signal('');
  readonly ocupado = signal(false);

  async entrar(): Promise<void> {
    if (this.ocupado() || !this.token().trim()) return;
    this.ocupado.set(true);
    this.error.set('');
    this.api.guardarToken(this.token().trim());
    this.token.set('');
    try {
      const actor = await this.api.cargarIdentidad();
      const destino = actor.roles.includes('JEFE_INMEDIATO') ? '/revision-jefe' :
        actor.roles.includes('TALENTO_HUMANO') ? '/talento-humano' : null;
      if (destino) await this.router.navigateByUrl(destino);
      else this.api.cerrarSesion('La identidad autenticada no tiene un rol de gestión o aprobación habilitado para este panel.');
    } catch (error) {
      this.error.set(mensajeError(error));
      if (this.api.autenticado()) this.api.cerrarSesion('No fue posible verificar el acceso. Introduce de nuevo el token.');
    } finally { this.ocupado.set(false); }
  }
}