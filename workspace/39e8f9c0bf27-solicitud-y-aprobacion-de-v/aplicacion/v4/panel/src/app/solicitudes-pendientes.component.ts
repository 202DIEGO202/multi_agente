import { CommonModule } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpHeaders, HttpClientModule } from '@angular/common/http';
import { Router } from '@angular/router';
import { catchError, finalize } from 'rxjs';

@Component({
  selector: 'app-solicitudes-pendientes',
  standalone: true,
  imports: [CommonModule, FormsModule, HttpClientModule],
  template: `
    <section class="p-4">
      <h1>Bandeja de revisión - Jefe inmediato</h1>
      <p *ngIf="error()" class="error">{{ error() }}</p>

      <div class="stack gap-4">
        <article>
          <h2>Solicitudes pendientes</h2>
          <ul>
            <li *ngFor="let s of solicitudes()" (click)="seleccionar(s)">
              {{ s.texto }}
            </li>
          </ul>
        </article>

        <article *ngIf="seleccionada() as s">
          <h2>Solicitud en revisión</h2>
          <div>Solicitante: {{ s.solicitante }}</div>
          <div>Área: {{ s.area }}</div>
          <div>Tipo de ausencia: {{ s.tipo }}</div>
          <div>Fechas: {{ s.fechas }}</div>
          <div>Observación del empleado: {{ s.observacion }}</div>

          <label>
            <span>Observaciones de revisión del jefe</span>
            <textarea [(ngModel)]="observacion"></textarea>
          </label>

          <button (click)="aprobar()" [disabled]="cargando()">Aprobar solicitud</button>
          <button (click)="rechazar()" [disabled]="cargando()">Rechazar solicitud</button>
        </article>
      </div>
    </section>
  `,
})
export class SolicitudesPendientesComponent implements OnInit {
  solicitudes = signal([{ texto: 'Solicitante: Laura Gómez | Tipo: Vacaciones | Fechas: 12/07/2026 - 19/07/2026', solicitante: 'Laura Gómez', area: 'Operaciones', tipo: 'Vacaciones', fechas: '12/07/2026 - 19/07/2026', observacion: 'Viaje familiar' }, { texto: 'Solicitante: Carlos Pérez | Tipo: Permiso personal | Fecha: 03/08/2026', solicitante: 'Carlos Pérez', area: 'Operaciones', tipo: 'Permiso personal', fechas: '03/08/2026', observacion: '' }]);
  seleccionada = signal<any>(null);
  observacion = '';
  error = signal('');
  cargando = signal(false);

  constructor(private http: HttpClient, private router: Router) {}

  ngOnInit(): void {
    if (!sessionStorage.getItem('admin_token')) this.router.navigateByUrl('/acceso');
  }

  headers() {
    const token = sessionStorage.getItem('admin_token') || '';
    return { headers: new HttpHeaders({ Authorization: `Bearer ${token}` }) };
  }

  seleccionar(s: any): void { this.seleccionada.set(s); }
  aprobar(): void { this.error.set(''); this.cargando.set(true); this.http.post('/api/admin/solicitudes/1/aprobar', { observacion: this.observacion }, this.headers()).pipe(catchError((e) => { if (e.status === 401) this.router.navigateByUrl('/acceso'); throw e; }), finalize(() => this.cargando.set(false))).subscribe(); }
  rechazar(): void { this.error.set(''); this.cargando.set(true); this.http.post('/api/admin/solicitudes/1/rechazar', { observacion: this.observacion }, this.headers()).pipe(catchError((e) => { if (e.status === 401) this.router.navigateByUrl('/acceso'); throw e; }), finalize(() => this.cargando.set(false))).subscribe(); }
}