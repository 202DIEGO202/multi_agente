import { CommonModule } from '@angular/common';
import { HttpClient, HttpClientModule, HttpHeaders } from '@angular/common/http';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

@Component({
  selector: 'app-acceso',
  standalone: true,
  imports: [CommonModule, FormsModule, HttpClientModule],
  template: `
    <section class="p-4">
      <h1>Acceso</h1>
      <p>Ingrese el token de administración para continuar.</p>

      <form class="stack gap-3" (ngSubmit)="guardar()">
        <label>
          <span>Token de administración</span>
          <input type="password" name="token" [(ngModel)]="token" />
        </label>
        <button type="submit">Ingresar</button>
      </form>

      <p *ngIf="mensaje()">{{ mensaje() }}</p>
    </section>
  `,
})
export class AccesoComponent implements OnInit {
  token = '';
  mensaje = signal('');

  constructor(private router: Router) {}

  ngOnInit(): void {
    if (sessionStorage.getItem('admin_token')) {
      this.router.navigateByUrl('/solicitudes-pendientes');
    }
  }

  guardar(): void {
    sessionStorage.setItem('admin_token', this.token.trim());
    this.router.navigateByUrl('/solicitudes-pendientes');
  }
}