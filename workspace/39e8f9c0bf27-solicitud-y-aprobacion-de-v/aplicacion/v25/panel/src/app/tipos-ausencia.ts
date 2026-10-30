import { Component, DestroyRef, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AdminApi, Page, TipoAusencia, errorMessage } from './admin-api';

@Component({
  selector: 'app-tipos-ausencia', standalone: true, imports: [FormsModule],
  template: `
    @if (api.authenticated()) {
      <section class="card">
        <h1>Administración de tipos de ausencia</h1>
        <button type="button" (click)="api.logout()">Cerrar sesión</button>
        @if (error()) { <p role="alert">{{ error() }}</p> }
        @if (message()) { <p role="status">{{ message() }}</p> }
        <h2>Catálogo de tipos de ausencia</h2>
        <button type="button" (click)="cargar()" [disabled]="busy()">Actualizar catálogo</button>
        @if (busy()) { <p role="status">Procesando…</p> }
        @if (!busy() && !items().length) { <p>No hay tipos de ausencia en esta página.</p> }
        <ul>
          @for (tipo of items(); track tipo.id) {
            <li>Tipo: {{ tipo.nombre }} | Estado: {{ tipo.estado === 'ACTIVO' ? 'Activo' : 'Inactivo' }} | Flujo: {{ flujoLabel(tipo.flujo_codigo) }}
              <button type="button" (click)="editar(tipo.id)" [disabled]="busy()">Editar</button>
            </li>
          }
        </ul>
        <button type="button" (click)="pagina(-1)" [disabled]="busy() || offset() === 0">Anterior</button>
        <span>Página {{ offset() / 50 + 1 }}</span>
        <button type="button" (click)="pagina(1)" [disabled]="busy() || items().length < 50">Siguiente</button>
        <h2>{{ id() === null ? 'Nuevo tipo de ausencia' : 'Editar tipo de ausencia' }}</h2>
        <button type="button" (click)="nuevo()" [disabled]="busy()">Nuevo tipo de ausencia</button>
        <form (ngSubmit)="guardar()">
          <label for="type-name">Nombre del tipo de ausencia</label>
          <input id="type-name" name="nombre" required maxlength="200" [ngModel]="nombre()" (ngModelChange)="nombre.set($event)" [disabled]="busy()">
          @if (!nombre().trim()) { <p>El nombre es obligatorio.</p> }
          <label for="type-state">Estado del tipo</label>
          <select id="type-state" name="estado" required [ngModel]="estado()" (ngModelChange)="estado.set($event)" [disabled]="busy()">
            <option value="ACTIVO">Activo</option><option value="INACTIVO">Inactivo</option>
          </select>
          <label for="type-flow">Flujo de aprobación</label>
          <select id="type-flow" name="flujo" required [ngModel]="flujo()" (ngModelChange)="flujo.set($event)" [disabled]="busy()">
            <option value="JEFE_INMEDIATO">Jefe inmediato</option>
            <option value="JEFE_Y_TALENTO_HUMANO">Jefe inmediato > Talento Humano</option>
            <option value="TALENTO_HUMANO">Talento Humano</option>
          </select>
          <label for="type-reason"><input id="type-reason" name="requiereMotivo" type="checkbox" [ngModel]="requiereMotivo()" (ngModelChange)="requiereMotivo.set($event)" [disabled]="busy()">Requiere motivo</label>
          <label for="type-hours">Modalidad de horas</label>
          <select id="type-hours" name="horas" [ngModel]="horas()" (ngModelChange)="horas.set($event)" [disabled]="busy()">
            <option value="NO_APLICA">No aplica</option><option value="OPCIONAL">Opcional</option><option value="OBLIGATORIA">Obligatoria</option>
          </select>
          <p>Las reglas de captura se validan en la API. Los cambios conservan las instantáneas de solicitudes existentes.</p>
          <button type="submit" [disabled]="busy() || !nombre().trim()">Guardar tipo de ausencia</button>
        </form>
      </section>
    }
  `
})
export class TiposAusenciaComponent {
  readonly api = inject(AdminApi);
  private readonly destroyRef = inject(DestroyRef);
  readonly items = signal<TipoAusencia[]>([]);
  readonly offset = signal(0);
  readonly id = signal<number | null>(null);
  readonly nombre = signal('');
  readonly estado = signal('ACTIVO');
  readonly flujo = signal('JEFE_INMEDIATO');
  readonly requiereMotivo = signal(false);
  readonly horas = signal('OPCIONAL');
  readonly busy = signal(false);
  readonly error = signal('');
  readonly message = signal('');

  ngOnInit(): void { void this.cargar(); }

  flujoLabel(code: string): string {
    return ({ JEFE_INMEDIATO: 'Jefe inmediato', JEFE_Y_TALENTO_HUMANO: 'Jefe inmediato > Talento Humano', TALENTO_HUMANO: 'Talento Humano' } as Record<string, string>)[code] || code;
  }

  nuevo(): void {
    this.id.set(null); this.nombre.set(''); this.estado.set('ACTIVO');
    this.flujo.set('JEFE_INMEDIATO'); this.requiereMotivo.set(false); this.horas.set('OPCIONAL');
  }

  async cargar(): Promise<void> {
    if (this.busy()) return;
    this.busy.set(true); this.error.set(''); this.items.set([]);
    try {
      const page = await this.api.request<Page<TipoAusencia>>(`tipos-ausencia?limite=50&desplazamiento=${this.offset()}`);
      if (!this.destroyRef.destroyed && this.api.authenticated()) this.items.set(page.items);
    } catch (error) { this.error.set(errorMessage(error)); }
    finally { this.busy.set(false); }
  }

  pagina(direction: number): void {
    this.offset.update(value => Math.max(0, value + direction * 50));
    void this.cargar();
  }

  async editar(id: number): Promise<void> {
    if (this.busy()) return;
    this.busy.set(true); this.error.set(''); this.message.set('');
    try {
      const tipo = await this.api.request<TipoAusencia>(`tipos-ausencia/${id}`);
      if (this.destroyRef.destroyed || !this.api.authenticated()) return;
      this.id.set(tipo.id); this.nombre.set(tipo.nombre); this.estado.set(tipo.estado);
      this.flujo.set(tipo.flujo_codigo); this.requiereMotivo.set(tipo.requiere_motivo); this.horas.set(tipo.modalidad_horas);
    } catch (error) { this.error.set(errorMessage(error)); }
    finally { this.busy.set(false); }
  }

  async guardar(): Promise<void> {
    if (this.busy() || !this.nombre().trim()) return;
    this.busy.set(true); this.error.set(''); this.message.set('');
    let saved = false;
    try {
      const id = this.id();
      await this.api.request<TipoAusencia>(id === null ? 'tipos-ausencia' : `tipos-ausencia/${id}`, id === null ? 'POST' : 'PUT', {
        nombre: this.nombre().trim(), estado: this.estado(), flujo_codigo: this.flujo(),
        requiere_motivo: this.requiereMotivo(), modalidad_horas: this.horas()
      });
      if (!this.destroyRef.destroyed && this.api.authenticated()) {
        this.message.set('Tipo de ausencia guardado.'); this.nuevo(); saved = true;
      }
    } catch (error) { this.error.set(errorMessage(error)); }
    finally { this.busy.set(false); }
    if (saved) await this.cargar();
  }
}