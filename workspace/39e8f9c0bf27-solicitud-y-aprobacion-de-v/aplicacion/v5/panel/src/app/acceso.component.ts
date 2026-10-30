import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  standalone: true,
  selector: 'app-acceso',
  imports: [CommonModule, FormsModule],
  template: `
    <section class="card p-4 max-w-xl mx-auto">
      <h1 class="text-xl font-semibold mb-4">Acceso</h1>

      <p class="mb-4 text-sm text-red-700" *ngIf="mensaje()">{{ mensaje() }}</p>

      <label class="block mb-2 font-medium" for="token">Token de administración</label>
      <input
        id="token"
        type="password"
        class="input w-full mb-4"
        [ngModel]="token()"
        (ngModelChange)="token.set($event)"
        autocomplete="current-password"
      />

      <div class="flex gap-2">
        <button class="btn btn-primary" type="button" (click)="guardar()">Guardar token</button>
        <button class="btn" type="button" (click)="limpiar()">Limpiar</button>
      </div>

      <p class="mt-4 text-sm" *ngIf="hayToken()">Token almacenado en esta sesión.</p>
    </section>
  `,
})
export class AccesoComponent {
  readonly token = signal('');
  readonly mensaje = signal('');
  readonly hayToken = computed(() => !!sessionStorage.getItem('admin_token'));

  guardar(): void {
    sessionStorage.setItem('admin_token', this.token().trim());
    this.mensaje.set('');
  }

  limpiar(): void {
    sessionStorage.removeItem('admin_token');
    this.token.set('');
    this.mensaje.set('');
  }
}