import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

@Component({
  selector: 'app-access',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="container">
      <h1>Acceso administrativo</h1>
      <form (ngSubmit)="onSubmit()" #form="ngForm" class="form">
        <label for="token">Token de administración</label>
        <input
          id="token"
          name="token"
          type="password"
          [(ngModel)]="tokenValue"
          required
          autocomplete="off"
          class="input"
        />
        <button type="submit" class="btn btn-primary" [disabled]="!tokenValue">Ingresar</button>
      </form>
      <p *ngIf="errorMessage()" class="error">{{ errorMessage() }}</p>
    </div>
  `,
})
export class AccessComponent {
  tokenValue = '';
  errorMessage = signal('');

  constructor(private router: Router) {
    // Si ya hay token en sessionStorage, redirigir a lista
    const stored = sessionStorage.getItem('admin_token');
    if (stored) {
      this.router.navigate(['/approval', 'latest']);
    }
  }

  onSubmit() {
    // Guardar token en sessionStorage y navegar a lista
    sessionStorage.setItem('admin_token', this.tokenValue);
    this.errorMessage.set('');
    this.router.navigate(['/approval', 'latest']);
  }
}