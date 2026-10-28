import { importProvidersFrom, signal } from '@angular/core';
import { provideRouter, Route } from '@angular/router';
import { HttpClientModule, HttpClient, HttpHeaders, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { AppComponent } from './app.component';
import { ApprovalComponent } from './approval.component';

// Servicio para manejar token y llamadas API con autorización
class AdminApiService {
  private http = inject(HttpClient);
  private tokenSignal = signal<string | null>(sessionStorage.getItem('admin_token'));

  get token() {
    return this.tokenSignal();
  }

  set token(value: string | null) {
    if (value) {
      sessionStorage.setItem('admin_token', value);
    } else {
      sessionStorage.removeItem('admin_token');
    }
    this.tokenSignal.set(value);
  }

  get<T>(url: string) {
    if (!this.token) {
      return throwError(() => new Error('No autorizado: sin token'));
    }
    const headers = new HttpHeaders({ Authorization: `Bearer ${this.token}` });
    return this.http.get<T>(url, { headers }).pipe(
      catchError((err: HttpErrorResponse) => {
        if (err.status === 401) {
          this.token = null;
          return throwError(() => new Error('Token inválido o expirado. Por favor, ingrese el token nuevamente.'));
        }
        return throwError(() => err);
      })
    );
  }

  post<T>(url: string, body: any) {
    if (!this.token) {
      return throwError(() => new Error('No autorizado: sin token'));
    }
    const headers = new HttpHeaders({ Authorization: `Bearer ${this.token}` });
    return this.http.post<T>(url, body, { headers }).pipe(
      catchError((err: HttpErrorResponse) => {
        if (err.status === 401) {
          this.token = null;
          return throwError(() => new Error('Token inválido o expirado. Por favor, ingrese el token nuevamente.'));
        }
        return throwError(() => err);
      })
    );
  }
}

// Rutas
export const routes: Route[] = [
  { path: '', component: AppComponent },
  { path: 'approval/:id', component: ApprovalComponent },
  { path: '**', redirectTo: '' }
];

// Exportar App y routes
export { AppComponent as App, routes };