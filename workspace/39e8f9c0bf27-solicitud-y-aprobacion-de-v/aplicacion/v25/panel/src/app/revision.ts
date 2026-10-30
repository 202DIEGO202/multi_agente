import { Directive, DestroyRef, inject, signal, computed } from '@angular/core';
import { AdminApi, ApiError, Page, Solicitud, errorMessage } from './admin-api';

export const revisionTemplate = `
  @if (api.authenticated()) {
    <section class="card">
      <h1>{{ titulo }}</h1>
      <button type="button" (click)="api.logout()">Cerrar sesión</button>
      @if (rol === 'TALENTO_HUMANO') {
        <section><h2>Revisor de Talento Humano</h2><p>Identidad autenticada mediante el JWT del aprobador. La API verifica el rol y la asignación en cada operación.</p></section>
      }
      @if (error()) { <p role="alert">{{ error() }}</p> }
      @if (message()) { <p role="status">{{ message() }}</p> }
      <h2>Solicitudes pendientes</h2>
      <p>Solicitudes asignadas a su identidad. Seleccione una para comprobar la etapa del flujo aplicable.</p>
      <button type="button" (click)="cargar()" [disabled]="busy()">Actualizar bandeja</button>
      @if (busy()) { <p role="status">Cargando…</p> }
      @if (!busy() && !items().length) { <p>No hay solicitudes pendientes en esta página.</p> }
      <ul>
        @for (s of items(); track s.id) {
          <li><button type="button" (click)="seleccionar(s.id)" [disabled]="busy() || deciding()">
            Solicitud #{{ s.id }} | Solicitante: {{ s.solicitante?.nombre || ('#' + s.solicitante_id) }} |
            Tipo: {{ s.tipo_ausencia_nombre || ('#' + s.tipo_ausencia_id) }} | Fechas: {{ s.fecha_inicio }} - {{ s.fecha_fin }}
          </button></li>
        }
      </ul>
      <button type="button" (click)="pagina(-1)" [disabled]="offset() === 0 || busy() || deciding()">Anterior</button>
      <span>Página {{ offset() / 50 + 1 }}</span>
      <button type="button" (click)="pagina(1)" [disabled]="items().length < 50 || busy() || deciding()">Siguiente</button>
      @if (selected(); as s) {
        <section class="card">
          <h2>{{ rol === 'TALENTO_HUMANO' ? 'Solicitud a validar' : 'Solicitud en revisión' }}</h2>
          <dl>
            <dt>Solicitante</dt><dd>{{ s.solicitante?.nombre || ('#' + s.solicitante_id) }}</dd>
            <dt>Área</dt><dd>{{ s.solicitante?.area || 'No informada' }}</dd>
            <dt>Tipo de ausencia</dt><dd>{{ s.tipo_ausencia_nombre || ('#' + s.tipo_ausencia_id) }}</dd>
            <dt>Fechas</dt><dd>{{ s.fecha_inicio }} - {{ s.fecha_fin }}</dd>
            <dt>Horas</dt><dd>{{ s.hora_inicio || 'No aplica' }} - {{ s.hora_fin || 'No aplica' }}</dd>
            <dt>Observación del empleado</dt><dd>{{ s.motivo || 'Sin observación' }}</dd>
            <dt>Estado</dt><dd>{{ s.estado_codigo }}</dd>
            <dt>Versión</dt><dd>{{ s.version }}</dd>
            @if (rol === 'TALENTO_HUMANO') {
              <dt>Caso requiere revisión adicional</dt><dd>{{ requiereTalento() ? 'Sí' : 'No' }}</dd>
            }
          </dl>
          <h3>Observación previa</h3>
          @for (o of s.observaciones || []; track o.id) { <p>{{ o.texto }} — {{ o.creado_en }} · Autor #{{ o.autor_id }}</p> }
          @if (!s.observaciones?.length) { <p>Sin observaciones previas.</p> }
          @if (revision()) {
            <form (ngSubmit)="decidir(rol === 'TALENTO_HUMANO' ? 'VALIDAR_APROBAR' : 'APROBAR')">
              <label for="review-observation">{{ etiquetaObservacion }}</label>
              <textarea id="review-observation" name="observacion" maxlength="4000" [ngModel]="observation()" (ngModelChange)="observation.set($event)" [disabled]="deciding()"></textarea>
              <p>La observación es obligatoria para rechazar.</p>
              <button type="submit" [disabled]="deciding()">{{ rol === 'TALENTO_HUMANO' ? 'Validar y aprobar' : 'Aprobar solicitud' }}</button>
              <button type="button" (click)="decidir('RECHAZAR')" [disabled]="deciding() || !observation().trim()">Rechazar solicitud</button>
            </form>
          } @else { <p>Esta solicitud no tiene una revisión pendiente de esta etapa. No puede decidir desde esta pantalla.</p> }
          <button type="button" (click)="cargarHistorial()" [disabled]="historyBusy() || deciding()">Consultar historial</button>
          @if (historyBusy()) { <p>Cargando historial…</p> }
          @if (history() !== null) {
            <h3>Historial de la solicitud</h3>
            @for (evento of history(); track $index) { <pre>{{ evento | json }}</pre> }
            @if (!history()?.length) { <p>Sin eventos.</p> }
            <button type="button" (click)="historialPagina(-1)" [disabled]="historyOffset() === 0 || historyBusy()">Eventos anteriores</button>
            <button type="button" (click)="historialPagina(1)" [disabled]="(history()?.length || 0) < 50 || historyBusy()">Eventos siguientes</button>
          }
        </section>
      }
    </section>
  }
`;

@Directive()
export abstract class RevisionScreen {
  readonly api = inject(AdminApi);
  readonly destroyRef = inject(DestroyRef);
  abstract readonly rol: string;
  abstract readonly titulo: string;
  abstract readonly etiquetaObservacion: string;
  readonly items = signal<Solicitud[]>([]);
  readonly selected = signal<Solicitud | null>(null);
  readonly offset = signal(0);
  readonly busy = signal(false);
  readonly deciding = signal(false);
  readonly error = signal('');
  readonly message = signal('');
  readonly observation = signal('');
  readonly history = signal<unknown[] | null>(null);
  readonly historyOffset = signal(0);
  readonly historyBusy = signal(false);
  private selectionSequence = 0;
  readonly revision = computed(() => {
    const s = this.selected();
    if (!s || s.estado_codigo !== 'EN_REVISION') return null;
    return s.revisiones?.find(r => r.estado === 'PENDIENTE' && r.rol_codigo === this.rol) || null;
  });
  readonly requiereTalento = computed(() => !!this.selected()?.revisiones?.some(r => r.rol_codigo === 'TALENTO_HUMANO'));

  ngOnInit(): void { void this.cargar(); }

  async cargar(): Promise<void> {
    if (this.busy() || this.deciding()) return;
    this.busy.set(true);
    this.error.set('');
    this.selected.set(null);
    this.history.set(null);
    this.selectionSequence++;
    this.items.set([]);
    try {
      const page = await this.api.request<Page<Solicitud>>(`solicitudes?pendientes=true&limite=50&desplazamiento=${this.offset()}`);
      if (!this.destroyRef.destroyed && this.api.authenticated()) this.items.set(page.items);
    } catch (error) { this.error.set(errorMessage(error)); }
    finally { this.busy.set(false); }
  }

  pagina(direction: number): void {
    this.offset.update(value => Math.max(0, value + direction * 50));
    void this.cargar();
  }

  async seleccionar(id: number): Promise<void> {
    const sequence = ++this.selectionSequence;
    this.busy.set(true);
    this.error.set('');
    this.selected.set(null);
    this.history.set(null);
    this.historyOffset.set(0);
    this.observation.set('');
    try {
      const solicitud = await this.api.request<Solicitud>(`solicitudes/${id}`);
      if (sequence === this.selectionSequence && !this.destroyRef.destroyed && this.api.authenticated()) this.selected.set(solicitud);
    } catch (error) { this.error.set(errorMessage(error)); }
    finally { if (sequence === this.selectionSequence) this.busy.set(false); }
  }

  async decidir(accion: 'APROBAR' | 'RECHAZAR' | 'VALIDAR_APROBAR'): Promise<void> {
    const s = this.selected();
    const r = this.revision();
    if (!s || !r || this.deciding()) return;
    const observacion = this.observation().trim();
    if (accion === 'RECHAZAR' && !observacion) { this.error.set('El rechazo requiere observaciones.'); return; }
    this.deciding.set(true);
    this.error.set('');
    this.message.set('');
    let refresh = false;
    try {
      await this.api.request<Solicitud>(`solicitudes/${s.id}/decisiones`, 'POST', {
        revision_id: r.id, version_esperada: s.version, accion,
        ...(observacion ? { observacion } : {})
      });
      this.message.set('Decisión registrada. Las observaciones se han guardado cuando fueron proporcionadas.');
      refresh = true;
    } catch (error) {
      this.error.set(errorMessage(error));
      if (error instanceof ApiError && error.status === 409) {
        this.message.set('La solicitud cambió durante la revisión. Se recargará el detalle; revise la nueva versión antes de decidir.');
        refresh = true;
      }
    } finally { this.deciding.set(false); }
    if (refresh && this.api.authenticated() && !this.destroyRef.destroyed) {
      await this.seleccionar(s.id);
      if (this.selected()?.estado_codigo !== 'EN_REVISION' || !this.revision()) this.items.update(rows => rows.filter(row => row.id !== s.id));
    }
  }

  async cargarHistorial(): Promise<void> {
    const s = this.selected();
    if (!s || this.historyBusy()) return;
    const sequence = this.selectionSequence;
    this.historyBusy.set(true);
    this.error.set('');
    try {
      const page = await this.api.request<Page<unknown>>(`solicitudes/${s.id}/historial?limite=50&desplazamiento=${this.historyOffset()}`);
      if (sequence === this.selectionSequence && !this.destroyRef.destroyed && this.api.authenticated()) this.history.set(page.items);
    } catch (error) { this.error.set(errorMessage(error)); }
    finally { this.historyBusy.set(false); }
  }

  historialPagina(direction: number): void {
    this.historyOffset.update(value => Math.max(0, value + direction * 50));
    void this.cargarHistorial();
  }
}