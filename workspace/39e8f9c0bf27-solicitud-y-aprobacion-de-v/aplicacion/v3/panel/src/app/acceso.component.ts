import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AdminApiService } from './shared/admin-api.service';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="p-4">
      <h1>Acceso</h1>
      <p>Ingresa el token de administración para ver datos del panel.</p>

      <label class="block">
        <span>Token de administración</span>
        <input type="password" class="input" [(ngModel)]="token" />
      </label>

      <div class="mt-3">
        <button type="button" (click)="guardar()">Entrar</button>
      </div>

      <p class="text-red-600" *ngIf="mensaje()">{{ mensaje() }}</p>
      <p class="text-red-600" *ngIf="api.authError()">{{ api.authError() }}</p>
    </section>
  `,
})
export class accesoComponent {
  private readonly router = inject(Router);
  readonly api = inject(AdminApiService);
  token = sessionStorage.getItem('admin_token') ?? '';
  readonly mensaje = signal('');

  guardar() {
    if (!this.token.trim()) {
      this.mensaje.set('Debes ingresar el token de administración.');
      return;
    }
    this.api.setToken(this.token);
    this.router.navigateByUrl('/bandeja-revision');
  }
}