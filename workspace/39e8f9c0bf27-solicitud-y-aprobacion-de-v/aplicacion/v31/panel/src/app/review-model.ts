import { DestroyRef, computed, inject, signal } from '@angular/core';
import { AdminApi, ApiError, Aviso, Historial, SolicitudDetalle, SolicitudLista } from './admin-api';

export class ReviewModel {
  readonly api = inject(AdminApi);
  private readonly abort = new AbortController();
  readonly items = signal<SolicitudLista[]>([]);
  readonly selected = signal<SolicitudDetalle | null>(null);
  readonly selectedSummary = signal<SolicitudLista | null>(null);
  readonly history = signal<Historial | null>(null);
  readonly notices = signal<Aviso[]>([]);
  readonly noticeError = signal('');
  readonly observation = signal('');
  readonly busy = signal(false);
  readonly message = signal('');
  readonly error = signal('');
  readonly offset = signal(0);
  readonly noticeOffset = signal(0);
  readonly currentStep = computed(() => this.selected()?.revisiones.filter(r => r.estado === 'PENDIENTE').sort((a, b) => a.orden - b.orden)[0]);
  readonly canDecide = computed(() => {
    const request = this.selected();
    return !!request && ['ENVIADA', 'EN_REVISION'].includes(request.estado_codigo) && this.currentStep()?.rol_codigo === this.role;
  });

  constructor(readonly role: 'JEFE_INMEDIATO' | 'TALENTO_HUMANO') {
    inject(DestroyRef).onDestroy(() => this.abort.abort());
    void this.load();
    void this.loadNotices();
  }

  private report(error: unknown) {
    if (!this.abort.signal.aborted) this.error.set(error instanceof Error ? error.message : 'No se pudo completar la operación.');
  }

  async load(offset = this.offset()) {
    if (this.busy()) return;
    this.busy.set(true); this.error.set('');
    this.selected.set(null); this.selectedSummary.set(null); this.history.set(null); this.observation.set('');
    try {
      const items = await this.api.request<SolicitudLista[]>(`solicitudes?pendientes=true&limite=50&offset=${offset}`, 'GET', undefined, this.abort.signal);
      this.items.set(items); this.offset.set(offset);
    } catch (error) { this.items.set([]); this.report(error); }
    finally { this.busy.set(false); }
  }

  async loadNotices(offset = this.noticeOffset()) {
    this.noticeError.set('');
    try {
      this.notices.set(await this.api.request<Aviso[]>(`notificaciones?limite=50&offset=${offset}`, 'GET', undefined, this.abort.signal));
      this.noticeOffset.set(offset);
    } catch (error) {
      this.notices.set([]);
      if (!this.abort.signal.aborted) this.noticeError.set(error instanceof Error ? error.message : 'No se pudieron consultar los avisos.');
    }
  }

  async open(item: SolicitudLista) {
    if (this.busy()) return;
    this.busy.set(true); this.error.set(''); this.message.set('');
    this.selected.set(null); this.history.set(null); this.observation.set(''); this.selectedSummary.set(item);
    try {
      this.selected.set(await this.api.request<SolicitudDetalle>(`solicitudes/${item.id}`, 'GET', undefined, this.abort.signal));
    } catch (error) { this.report(error); }
    finally { this.busy.set(false); }
  }

  async showHistory() {
    const item = this.selected();
    if (!item || this.busy()) return;
    this.busy.set(true); this.error.set(''); this.history.set(null);
    try { this.history.set(await this.api.request<Historial>(`solicitudes/${item.id}/historial`, 'GET', undefined, this.abort.signal)); }
    catch (error) { this.report(error); }
    finally { this.busy.set(false); }
  }

  async decide(action: 'APROBAR' | 'RECHAZAR' | 'VALIDAR_Y_APROBAR') {
    const item = this.selected();
    if (!item || this.busy() || !this.canDecide()) return;
    const observation = this.observation().trim();
    if (action === 'RECHAZAR' && !observation) { this.error.set('El motivo del rechazo es obligatorio. Registre las observaciones.'); return; }
    if (observation.length > 4000) { this.error.set('Las observaciones no pueden superar 4000 caracteres.'); return; }
    this.busy.set(true); this.error.set(''); this.message.set('');
    let refresh = false;
    try {
      await this.api.request(`solicitudes/${item.id}/decisiones`, 'POST', { version: item.version, accion: action, observacion: observation || null }, this.abort.signal);
      this.message.set('Decisión registrada correctamente.'); refresh = true;
    } catch (error) {
      this.report(error);
      if (error instanceof ApiError && error.status === 409) {
        this.message.set('La solicitud cambió. Se actualizó la bandeja; abra la solicitud y revise su nueva versión antes de decidir.');
        refresh = true;
      }
    } finally { this.busy.set(false); }
    if (refresh) { await this.load(); void this.loadNotices(); }
  }

  logout() { this.items.set([]); this.selected.set(null); this.history.set(null); this.notices.set([]); this.api.logout(); }
}