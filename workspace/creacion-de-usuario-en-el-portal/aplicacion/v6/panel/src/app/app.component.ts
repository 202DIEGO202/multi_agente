import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="container">
      <h1>Panel Administrativo</h1>
      <div *ngIf="!token()">
        <label for="tokenInput">Token de administración</label>
        <input id="tokenInput" type="password" [(ngModel)]="tokenInput" class="form-control" />
        <button (click)="login()" class="btn btn-primary mt-2">Ingresar</button>
        <p class="text-danger mt-2" *ngIf="errorMessage">{{ errorMessage }}</p>
      </div>
      <div *ngIf="token()">
        <p>Token cargado. <button (click)="logout()" class="btn btn-link">Cerrar sesión</button></p>
        <p>Para revisar solicitudes, navegue a la pantalla de aprobación con la ruta /approval/:id</p>
      </div>
    </div>
  `
})
export class AppComponent {
  tokenInput = '';
  token = signal<string | null>(sessionStorage.getItem('admin_token'));
  errorMessage = '';

  login() {
    if (this.tokenInput.trim().length === 0) {
      this.errorMessage = 'El token no puede estar vacío.';
      return;
    }
    // Guardar token en sessionStorage y signal
    sessionStorage.setItem('admin_token', this.tokenInput.trim());
    this.token.set(this.tokenInput.trim());
    this.errorMessage = '';
    this.tokenInput = '';
  }

  logout() {
    sessionStorage.removeItem('admin_token');
    this.token.set(null);
  }
}