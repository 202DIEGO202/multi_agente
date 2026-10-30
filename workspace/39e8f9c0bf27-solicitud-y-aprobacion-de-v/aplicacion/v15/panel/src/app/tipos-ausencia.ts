import { Component, DestroyRef, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AdminError, AdminSession } from './admin-session';

type Flujo = 'JEFE' | 'JEFE_TH' | 'TH';
type Estado = 'Activo' | 'Inactivo';
interface Tipo {
  id: number;
  nombre: string;
  estado: Estado;
  flujo_codigo: Flujo;
  requiere_motivo: boolean;
  permite_horas: boolean;
  version: number;
}

@Component({
  selector: 'app-tipos-ausencia',
  standalone: true,
  imports: [FormsModule],
  template: `
    @if (session.authenticated()) {
      <section class="page">
        <header class="page-header">
          <h1>Administración de tipos de ausencia</h1>
          <button class="btn" type="button" (click)="session.logout()">Cerrar sesión</button>
        </header>
        @if (error()) { <p class="alert" role="alert">{{ error() }}</p> }
        @if (message()) { <p class="alert" role="status">{{ message() }}</p> }
        <section class="card" [attr.aria-busy]="busy()">
          <h2>Catálogo de tipos de ausencia</h2>
          <button class="btn" type="button" (click)="cargar()" [disabled]="busy()">Actualizar catálogo</button>
          @if (busy()) { <p role="status">Cargando…</p> }
          @for (tipo of tipos(); track tipo.id) {
            <article class="card">
              <p>Tipo: {{ tipo.nombre }} | Estado: {{ tipo.estado }} | Flujo: {{ etiquetaFlujo(tipo.flujo_codigo) }}</p>
              <button class="btn" type="button" (click)="editar(tipo)" [disabled]="busy()">Editar tipo de ausencia</button>
            </article>
          } @empty {
            @if (!busy()) { <p>No hay tipos de ausencia en esta página.</p> }
          }
          <nav aria-label="Paginación del catálogo">
            <button class="btn" type="button" (click)="pagina(-1)" [disabled]="busy() || offset() === 0">Anterior</button>
            <span>Página {{ offset() / limite + 1 }}</span>
            <button class="btn" type="button" (click)="pagina(1)" [disabled]="busy() || tipos().length < limite">Siguiente</button>
          </nav>
        </section>
        <section class="card">
          <h2>{{ selected() ? 'Editar tipo de ausencia' : 'Crear tipo de ausencia' }}</h2>
          <button class="btn" type="button" (click)="nuevo()" [disabled]="busy()">Nuevo tipo de ausencia</button>
          <form (ngSubmit)="guardar()" #form="ngForm">
            <label for="tipo-nombre">Nombre del tipo de ausencia</label>
            <input id="tipo-nombre" name="nombre" required maxlength="200" [ngModel]="nombre()" (ngModelChange)="nombre.set($event)" [disabled]="busy()">
            <label for="tipo-estado">Estado del tipo</label>
            <select id="tipo-estado" name="estado" required [ngModel]="estado()" (ngModelChange)="estado.set($event)" [disabled]="busy()">
              <option value="Activo">Activo</option>
              <option value="Inactivo">Inactivo</option>
            </select>
            <label for="tipo-flujo">Flujo de aprobación</label>
            <select id="tipo-flujo" name="flujo" required [ngModel]="flujo()" (ngModelChange)="flujo.set($event)" [disabled]="busy()">
              <option value="JEFE">Jefe inmediato</option>
              <option value="JEFE_TH">Jefe inmediato > Talento Humano</option>
              <option value="TH">Talento Humano</option>
            </select>
            <label for="tipo-motivo">
              <input id="tipo-motivo" name="motivo" type="checkbox" [ngModel]="requiereMotivo()" (ngModelChange)="requiereMotivo.set($event)" [disabled]="busy()">
              Requiere motivo u observación
            </label>
            <label for="tipo-horas">
              <input id="tipo-horas" name="horas" type="checkbox" [ngModel]="permiteHoras()" (ngModelChange)="permiteHoras.set($event)" [disabled]="busy()">
              Permite horas
            </label>
            <button class="btn btn-primary" type="submit" [disabled]="busy() || form.invalid || !nombre().trim() || conflicto()">Guardar tipo de ausencia</button>
            @if (conflicto()) { <p>Actualice el catálogo y seleccione nuevamente el tipo antes de guardar.</p> }
          </form>
        </section>
      </section>
    }
  `
})
export class TiposAusencia {
  readonly session = inject(AdminSession);
  readonly tipos = signal<Tipo[]>([]);
  readonly selected = signal<Tipo | null>(null);
  readonly nombre = signal('');
  readonly estado = signal<Estado>('Activo');
  readonly flujo = signal<Flujo>('JEFE');
  readonly requiereMotivo = signal(false);
  readonly permiteHoras = signal(false);
  readonly conflicto = signal(false);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly message = signal('');
  readonly offset = signal(0);
  readonly limite = 50;
  private alive = true;

  constructor() {
    inject(DestroyRef).onDestroy(() => {
      this.alive = false;
      this.tipos.set([]);
      this.selected.set(null);
    });
    void this.cargar();
  }

  etiquetaFlujo(flujo: Flujo): string {
    return { JEFE: 'Jefe inmediato', JEFE_TH: 'Jefe inmediato > Talento Humano', TH: 'Talento Humano' }[flujo];
  }

  private report(error: unknown): void {
    if (!this.alive || !this.session.authenticated()) return;
    this.error.set(error instanceof Error ? error.message : 'No se pudo completar la operación.');
  }

  private limpiar(): void {
    this.selected.set(null);
    this.nombre.set('');
    this.estado.set('Activo');
    this.flujo.set('JEFE');
    this.requiereMotivo.set(false);
    this.permiteHoras.set(false);
    this.conflicto.set(false);
  }

  nuevo(): void {
    if (this.busy()) return;
    this.limpiar();
    this.error.set('');
    this.message.set('');
  }

  async cargar(): Promise<void> {
    if (this.busy() || !this.session.hasToken()) return;
    this.busy.set(true);
    this.error.set('');
    this.tipos.set([]);
    this.limpiar();
    try {
      const rows = await this.session.request<Tipo[]>(`/api/admin/tipos-ausencia?limite=${this.limite}&offset=${this.offset()}`);
      if (this.alive && this.session.authenticated()) this.tipos.set(rows);
    } catch (error) { this.report(error); }
    finally { this.busy.set(false); }
  }

  pagina(direction: number): void {
    if (this.busy()) return;
    this.offset.update(value => Math.max(0, value + direction * this.limite));
    this.message.set('');
    void this.cargar();
  }

  async editar(tipo: Tipo): Promise<void> {
    if (this.busy() || !this.session.hasToken()) return;
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    this.limpiar();
    try {
      const row = await this.session.request<Tipo>(`/api/admin/tipos-ausencia/${tipo.id}`);
      if (!this.alive || !this.session.authenticated()) return;
      this.selected.set(row);
      this.nombre.set(row.nombre);
      this.estado.set(row.estado);
      this.flujo.set(row.flujo_codigo);
      this.requiereMotivo.set(row.requiere_motivo);
      this.permiteHoras.set(row.permite_horas);
    } catch (error) { this.report(error); }
    finally { this.busy.set(false); }
  }

  async guardar(): Promise<void> {
    if (this.busy() || this.conflicto() || !this.session.hasToken()) return;
    const nombre = this.nombre().trim();
    if (!nombre || nombre.length > 200) {
      this.error.set('El Nombre del tipo de ausencia es obligatorio y admite hasta 200 caracteres.');
      return;
    }
    const selected = this.selected();
    const body = {
      nombre,
      estado: this.estado(),
      flujo_codigo: this.flujo(),
      requiere_motivo: this.requiereMotivo(),
      permite_horas: this.permiteHoras(),
      ...(selected ? { version_esperada: selected.version } : {})
    };
    this.busy.set(true);
    this.error.set('');
    this.message.set('');
    let recargar = false;
    try {
      await this.session.request<unknown>(
        selected ? `/api/admin/tipos-ausencia/${selected.id}` : '/api/admin/tipos-ausencia',
        selected ? 'PUT' : 'POST',
        body
      );
      if (!this.alive || !this.session.authenticated()) return;
      this.message.set('Tipo de ausencia y flujo de aprobación guardados.');
      this.limpiar();
      recargar = true;
    } catch (error) {
      if (selected && error instanceof AdminError && error.status === 409 && this.alive && this.session.authenticated()) {
        this.conflicto.set(true);
      }
      this.report(error);
    } finally { this.busy.set(false); }
    if (recargar) await this.cargar();
  }
}