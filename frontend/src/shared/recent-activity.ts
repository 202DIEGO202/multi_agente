import { Component, effect, inject, signal, untracked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Store } from '../core/store';
import { Execution } from '../core/models';
import { Icon } from './icon';

@Component({selector:'recent-activity',standalone:true,imports:[CommonModule,RouterLink,Icon],template:`
<section class="card baseline-section"><div class="section-heading"><h2>Actividad reciente</h2><a routerLink="/activity" class="text-link">Ver monitor<ui-icon name="arrow"/></a></div>
@for(run of runs();track run.id_ejecucion){<a class="baseline-row" routerLink="/activity" [queryParams]="{run:run.id_ejecucion}"><span class="stat-icon sage"><ui-icon [name]="run.tipo==='chat'?'chat':run.tipo==='ingesta'?'book':'flow'"/></span><strong>{{run.tipo==='chat'?'Análisis funcional':run.tipo==='ingesta'?'Ingesta documental':run.tipo==='backlog'?'Backlog funcional':run.tipo==='mockups'?'Diseño y mockups':run.tipo==='conocimiento'?'Base de conocimiento':run.tipo==='revision'?'Revisión de procedimientos':'Recuperación RAG'}}</strong><span>{{run.fecha|date:'dd MMM, HH:mm'}}</span><span class="pill">{{run.estado}}</span></a>}@empty{<p class="muted tiny">Las primeras ejecuciones de tu proyecto aparecerán aquí.</p>}</section>`})
export class RecentActivity {
  store=inject(Store);runs=signal<Execution[]>([]);private project='';
  constructor(){effect(()=>{const id=this.store.project()?.id_proyecto;untracked(()=>{if(!id){this.project='';this.runs.set([]);}else if(id!==this.project){this.project=id;void this.load();}});});}
  async load(){const base=this.store.base();try{const rows=await this.store.api.request<Execution[]>(`${base}/executions`);if(this.store.project()&&base===this.store.base())this.runs.set(rows.slice(0,4));}catch(error){this.store.api.showError(error);}}
}
