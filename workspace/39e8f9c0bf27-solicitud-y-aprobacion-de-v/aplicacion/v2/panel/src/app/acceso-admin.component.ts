import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

@Component({
  selector: 'app-acceso-admin',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="p-4">
      <h1>Acceso</h1>
      <p>Ingresa el Token de administración para continuar.</p>

      <p *ngIf="mensaje()" class="text-danger">{{ mensaje() }}</p>

      <label for="token">Token de administración</label>
      <input id="token" type="password" [(ngModel)]="token" class="form-control" />

      <div class="mt-3">
        <button type="button" class="btn btn-primary" (click)="guardar()">Ingresar</button>
        <button type="button" class="btn btn-secondary ms-2" (click)="limpiar()">Limpiar</button>
      </div>
    </section>
  `,
})
export class AccesoAdminComponent {
  private router = inject(Router);
  token = '';
  mensaje = signal('');

  guardar(): void {
    sessionStorage.setItem('admin_token', this.token.trim());
    this.mensaje.set('Token guardado en esta sesión.');
    void this.router.navigateByUrl('/bandeja-revision');
  }

  limpiar(): void {
    sessionStorage.removeItem('admin_token');
    this.token = '';
    this.mensaje.set('Sesión administrativa limpiada.');
  }
}