import { Injectable, computed, inject, signal } from '@angular/core';
import { ApiService } from './api.service';
import { Conversation, Project, ProjectState } from './models';

@Injectable({providedIn:'root'})
export class Store {
  api = inject(ApiService);
  projects = signal<Project[]>([]);
  project = signal<Project | null>(null);
  conversations = signal<Conversation[]>([]);
  conversationId = signal('');
  state = signal<ProjectState | null>(null);
  activeItems = computed(() => this.state()?.elementos.filter(i => i.vigencia === 'vigente') || []);
  pending = computed(() => this.state()?.propuestas.filter(p => ['propuesto','pendiente_aclaracion'].includes(p.estado)) || []);
  base() { return `/projects/${this.project()!.id_proyecto}`; }
  async init() {
    try {
      this.projects.set(await this.api.request<Project[]>('/projects'));
      const saved = localStorage.getItem('fabrica_project');
      const project = this.projects().find(p => p.id_proyecto === saved) || this.projects()[0];
      if (project) await this.select(project.id_proyecto);
    } catch (error) { this.api.showError(error); }
  }
  async select(id: string) {
    const project = this.projects().find(p => p.id_proyecto === id);
    if (!project) return;
    this.project.set(project); this.state.set(null); this.conversationId.set(''); this.conversations.set([]);
    localStorage.setItem('fabrica_project', id);
    try {
      await this.refresh();
      const conversations = await this.api.request<Conversation[]>(`${this.base()}/conversations`);
      if (this.project()?.id_proyecto !== id) return;
      this.conversations.set(conversations);
      const previous = localStorage.getItem(`fabrica_conversation_${id}`);
      this.openConversation(conversations.find(c => c.id === previous)?.id || conversations[0]?.id || '');
    } catch (error) { this.api.showError(error); }
  }
  clearProject() {
    this.project.set(null); this.state.set(null); this.conversations.set([]); this.conversationId.set('');
    localStorage.removeItem('fabrica_project');
  }
  async deleteProject(id: string) {
    await this.api.request(`/projects/${id}`, 'DELETE');
    const wasCurrent=this.project()?.id_proyecto===id;
    this.projects.update(rows=>rows.filter(project=>project.id_proyecto!==id));
    if(wasCurrent){this.clearProject();if(this.projects().length)await this.select(this.projects()[0].id_proyecto);}
  }
  async restoreProject(id:string) {
    await this.api.request(`/projects/${id}/restore`, 'POST');
    this.projects.set(await this.api.request<Project[]>('/projects'));
    if(!this.project())await this.select(id);
  }
  openConversation(id: string) {
    this.conversationId.set(id);
    if (this.project()) localStorage.setItem(`fabrica_conversation_${this.project()!.id_proyecto}`, id);
  }
  async newConversation() {
    const conversation = await this.api.request<Conversation>(`${this.base()}/conversations`, 'POST');
    this.conversations.update(rows => [conversation, ...rows]);
    this.openConversation(conversation.id);
    return conversation.id;
  }
  async refresh() {
    if (!this.project()) return;
    const id = this.project()!.id_proyecto;
    const state = await this.api.request<ProjectState>(`${this.base()}/state`);
    if (id === this.project()?.id_proyecto) { this.state.set(state); this.project.set(state.proyecto); }
  }
}
