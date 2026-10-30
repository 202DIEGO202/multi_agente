import { CommonModule } from '@angular/common';
import { Component, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

@Component({
  selector: 'app-acceso',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="p-4">
      <h1>Acceso</h1>
      <p class="mt-2">Ingresa el Token de administración para continuar.</p>

      <form class="mt-4" (ngSubmit)="guardar()">
        <label class="block mb-2" for="token">Token de administración</label>
        <input
          id="token"
          name="token"
          type="password"
          class="w-full"
          [(ngModel)]="token"
          autocomplete="current-password"
        />
        <button type="submit" class="mt-3">Entrar</button>
      </form>

      <p *ngIf="mensaje()" class="mt-3">{{ mensaje() }}</p>
    </section>
  `,
})
export class AccesoComponent {
  token = '';
  private readonly _mensaje = signal('');
  mensaje = computed(() => this._mensaje());

  constructor(private readonly router: Router) {}

  guardar(): void {
    sessionStorage.setItem('admin_token', this.token.trim());
    this._mensaje.set('Token guardado en esta sesión.');
    void this.router.navigateByUrl('/bandeja-revision');
  }
}