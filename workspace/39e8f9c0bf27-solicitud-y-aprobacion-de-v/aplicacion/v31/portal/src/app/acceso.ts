import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { PortalApi, mensajeError } from './portal-api';

@Component({
  selector: 'app-acceso',
  standalone: true,
  imports: [FormsModule],
  template: `
    <h1>Acceso</h1>
    <section class="card">
      <p>Identifíquese con su documento para consultar y registrar sus propias solicitudes.</p>
      <form (ngSubmit)="entrar()" novalidate>
        <label class="field">Documento <span aria-label="obligatorio">*</span>
          <input name="documento" autocomplete="username" required maxlength="100"
            [ngModel]="documento()" (ngModelChange)="cambiarDocumento($event)"
            [disabled]="ocupado()" aria-describedby="error-acceso">
        </label>
        @if (error()) { <p id="error-acceso" class="error" role="alert">{{ error() }}</p> }
        <button type="submit" [disabled]="ocupado()">{{ ocupado() ? 'Identificando…' : 'Acceder' }}</button>
      </form>
    </section>
  `
})
export class AccesoComponent {
  private readonly api = inject(PortalApi);
  private readonly router = inject(Router);
  readonly documento = signal('');
  readonly ocupado = signal(false);
  readonly error = signal('');

  cambiarDocumento(valor: string): void {
    this.documento.set(valor);
    this.error.set('');
  }

  async entrar(): Promise<void> {
    if (this.ocupado()) return;
    const documento = this.documento().trim();
    if (!documento) {
      this.error.set('El documento es obligatorio.');
      return;
    }
    if (documento.length > 100) {
      this.error.set('El documento debe tener como máximo 100 caracteres.');
      return;
    }
    this.ocupado.set(true);
    this.error.set('');
    try {
      await this.api.acceder(documento);
      await this.router.navigate(['/']);
    } catch (error) {
      this.error.set(mensajeError(error));
    } finally {
      this.ocupado.set(false);
    }
  }
}