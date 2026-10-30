import { Component, DestroyRef, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AdminApi, Flujo, TipoAusencia } from './admin-api';

@Component({
  selector: 'app-tipos-ausencia', standalone: true, imports: [FormsModule],
  template: `
    @if (api.authenticated()) {
      <section class="page">
        <h1>Administración de tipos de ausencia</h1>
        <button type="button" (click)="api.logout()">Cerrar sesión</button>
        @if (error()) { <p role="alert" class="alert">{{ error() }}</p> }
        @if (message()) { <p role="status">{{ message() }}</p> }
        @if (busy()) { <p role="status">Cargando…</p> }
        <section class="card">
          <h2>Catálogo de tipos de ausencia</h2>
          <button type="button" (click)="load()" [disabled]="busy()">Actualizar catálogo</button>
          <button type="button" (click)="reset()" [disabled]="busy() || !ready()">Nuevo tipo de ausencia</button>
          @for (tipo of tipos(); track tipo.id) {
            <article class="card">
              <p>Tipo: {{ tipo.nombre }} | Estado: {{ tipo.estado === 'ACTIVO' ? 'Activo' : 'Inactivo' }} | Flujo: {{ flowLabel(tipo.flujo_codigo) }}</p>
              <p>Motivo obligatorio: {{ tipo.requiere_motivo ? 'Sí' : 'No' }} | Permite horas: {{ tipo.permite_horas ? 'Sí' : 'No' }}</p>
              <button type="button" (click)="edit(tipo.id)" [disabled]="busy()">Editar tipo de ausencia</button>
            </article>
          } @empty { @if (!busy() && ready()) { <p>No hay tipos de ausencia registrados.</p> } }
        </section>
        @if (ready()) {
          <form class="card" (ngSubmit)="save()" #form="ngForm">
            <h2>{{ editingId() === null ? 'Nuevo tipo de ausencia' : 'Editar tipo de ausencia' }}</h2>
            <label for="tipo-nombre">Nombre del tipo de ausencia</label>
            <input id="tipo-nombre" name="nombre" required maxlength="150" [ngModel]="nombre()" (ngModelChange)="nombre.set($event)" [disabled]="busy()">
            <label for="tipo-estado">Estado del tipo</label>
            <select id="tipo-estado" name="estado" required [ngModel]="estado()" (ngModelChange)="estado.set($event)" [disabled]="busy()">
              <option value="ACTIVO">Activo</option><option value="INACTIVO">Inactivo</option>
            </select>
            <label for="tipo-flujo">Flujo de aprobación</label>
            <select id="tipo-flujo" name="flujo" required [ngModel]="flujo()" (ngModelChange)="flujo.set($event)" [disabled]="busy()">
              <option value="" disabled>Seleccione un flujo</option>
              @for (item of flujos(); track item.codigo) { <option [value]="item.codigo">{{ flowLabel(item.codigo) }}</option> }
            </select>
            <label for="tipo-motivo"><input id="tipo-motivo" name="motivo" type="checkbox" [ngModel]="requiereMotivo()" (ngModelChange)="requiereMotivo.set($event)" [disabled]="busy()"> Requiere motivo u observación</label>
            <label for="tipo-horas"><input id="tipo-horas" name="horas" type="checkbox" [ngModel]="permiteHoras()" (ngModelChange)="permiteHoras.set($event)" [disabled]="busy()"> Permite horas</label>
            <p>Los cambios no alteran la política capturada en solicitudes existentes.</p>
            <button type="submit" [disabled]="busy() || form.invalid || !nombre().trim() || !flujo()">Guardar tipo de ausencia</button>
            @if (editingId() !== null) { <button type="button" (click)="reset()" [disabled]="busy()">Cancelar edición</button> }
          </form>
        }
      </section>
    }
  `
})
export class TiposAusenciaComponent {
  readonly api = inject(AdminApi);
  private readonly abort = new AbortController();
  readonly tipos = signal<TipoAusencia[]>([]);
  readonly flujos = signal<Flujo[]>([]);
  readonly ready = signal(false);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly message = signal('');
  readonly editingId = signal<number | null>(null);
  readonly nombre = signal('');
  readonly estado = signal<'ACTIVO' | 'INACTIVO'>('ACTIVO');
  readonly flujo = signal('');
  readonly requiereMotivo = signal(false);
  readonly permiteHoras = signal(false);

  constructor() {
    inject(DestroyRef).onDestroy(() => this.abort.abort());
    void this.load();
  }

  flowLabel(code: string): string {
    const labels: Record<string, string> = {
      JEFE_INMEDIATO: 'Jefe inmediato',
      JEFE_Y_TALENTO_HUMANO: 'Jefe inmediato > Talento Humano',
      TALENTO_HUMANO: 'Talento Humano'
    };
    return labels[code] ?? this.flujos().find(item => item.codigo === code)?.nombre ?? code;
  }

  reset() {
    this.editingId.set(null); this.nombre.set(''); this.estado.set('ACTIVO');
    this.flujo.set(''); this.requiereMotivo.set(false); this.permiteHoras.set(false);
  }

  private report(error: unknown) {
    if (!this.abort.signal.aborted) this.error.set(error instanceof Error ? error.message : 'No se pudo completar la operación.');
  }

  async load() {
    if (this.busy()) return;
    this.busy.set(true); this.error.set(''); this.ready.set(false);
    try {
      const [tipos, flujos] = await Promise.all([
        this.api.request<TipoAusencia[]>('tipos-ausencia', 'GET', undefined, this.abort.signal),
        this.api.request<Flujo[]>('flujos', 'GET', undefined, this.abort.signal)
      ]);
      this.tipos.set(tipos); this.flujos.set(flujos); this.reset(); this.ready.set(true);
    } catch (error) { this.tipos.set([]); this.flujos.set([]); this.report(error); }
    finally { this.busy.set(false); }
  }

  async edit(id: number) {
    if (this.busy()) return;
    this.busy.set(true); this.error.set(''); this.message.set('');
    try {
      const item = await this.api.request<TipoAusencia>(`tipos-ausencia/${id}`, 'GET', undefined, this.abort.signal);
      this.editingId.set(item.id); this.nombre.set(item.nombre); this.estado.set(item.estado);
      this.flujo.set(item.flujo_codigo); this.requiereMotivo.set(item.requiere_motivo); this.permiteHoras.set(item.permite_horas);
    } catch (error) { this.report(error); }
    finally { this.busy.set(false); }
  }

  async save() {
    if (this.busy() || !this.ready()) return;
    if (!this.nombre().trim() || this.nombre().trim().length > 150 || !this.flujos().some(item => item.codigo === this.flujo())) {
      this.error.set('Indique un nombre válido y seleccione un flujo de aprobación disponible.'); return;
    }
    this.busy.set(true); this.error.set(''); this.message.set('');
    let saved = false;
    try {
      const id = this.editingId();
      await this.api.request(id === null ? 'tipos-ausencia' : `tipos-ausencia/${id}`, id === null ? 'POST' : 'PUT', {
        nombre: this.nombre().trim(), estado: this.estado(), requiere_motivo: this.requiereMotivo(),
        permite_horas: this.permiteHoras(), flujo_codigo: this.flujo()
      }, this.abort.signal);
      this.message.set('Tipo de ausencia guardado correctamente.'); saved = true;
    } catch (error) { this.report(error); }
    finally { this.busy.set(false); }
    if (saved) { this.reset(); await this.load(); }
  }
}