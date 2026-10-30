import { Injectable, signal } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class AdminApiService {
  private readonly token = signal(sessionStorage.getItem('admin_token') ?? '');
  readonly authError = signal('');

  constructor(private readonly http: HttpClient) {}

  setToken(token: string) {
    this.token.set(token.trim());
    sessionStorage.setItem('admin_token', this.token());
    this.authError.set('');
  }

  clearToken() {
    this.token.set('');
    sessionStorage.removeItem('admin_token');
  }

  private headers() {
    return new HttpHeaders({ Authorization: `Bearer ${this.token()}` });
  }

  private handleAuthError(error: any) {
    if (error?.status === 401) {
      this.clearToken();
      this.authError.set('La sesión administrativa no es válida. Vuelve a ingresar el token.');
    }
    return throwError(() => error);
  }

  get<T>(path: string) {
    return this.http.get<T>(`/api/admin${path}`, { headers: this.headers() }).pipe(
      catchError((error) => this.handleAuthError(error)),
    );
  }

  post<T>(path: string, body: unknown) {
    return this.http.post<T>(`/api/admin${path}`, body, { headers: this.headers() }).pipe(
      catchError((error) => this.handleAuthError(error)),
    );
  }
}