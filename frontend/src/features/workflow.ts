import { Component, effect, inject, OnDestroy, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Store } from '../core/store';
import { Icon } from '../shared/icon';

@Component({standalone:true, imports:[CommonModule,FormsModule,RouterLink,Icon], template:`
<div class="page"><div class="page-heading"><div><div class="eyebrow">DESARROLLO INTEGRAL</div>
<h1>De la necesidad al producto.</h1><p class="muted">Un flujo conserva el contexto, las decisiones y las versiones de todas las etapas.</p></div></div>
<div class="gentle-note"><ui-icon name="flow"/><p><strong>¿Cómo funciona?</strong> Cuenta lo que necesitas, revisa y aprueba cada etapa que el equipo de IA va preparando (requisitos, historias, diseño, arquitectura, código) y al final tendrás tu producto construido y probado.</p></div>
@if(store.project();as p){
<section class="card"><div class="section-heading"><h2>Preparar el trabajo</h2><span class="pill">Manual con revisión</span></div>
<p>Comparte una primera idea. El analista la retoma en el chat para precisar contigo los requisitos; cuando los apruebes, las demás etapas (historias, diseño, arquitectura, código) continúan solas, siempre con tu revisión.</p>
<label>Tu primera idea<textarea [(ngModel)]="objective" rows="5" maxlength="12000" placeholder="Por ejemplo: una app para que los empleados soliciten vacaciones y su jefe las apruebe. En el chat profundizamos quién la usa, qué problema resuelve y las reglas del negocio."></textarea></label>
<label class="mockup-check"><input type="checkbox" [(ngModel)]="deployLocal"/>Al terminar, iniciar también la instancia local verificada.</label>
<p class="muted tiny">Generar utiliza los modelos por API. Consultar el avance y aprobar no consume tokens. Las dudas no se responden inventando reglas del negocio. Después de empezar, sigues la conversación en el chat del analista.</p>
<button class="button primary" [disabled]="busy()||active()||objective.trim().length<15" (click)="start()">{{busy()?'Iniciando…':'Empezar con el analista'}}</button>
</section>
@if(runs().length){<div class="section-heading"><h2>Flujos del proyecto</h2><select aria-label="Seleccionar flujo" [ngModel]="selected()" (ngModelChange)="choose($event)">@for(r of runs();track r.id){<option [value]="r.id">{{r.fecha|date:'dd/MM HH:mm'}} · {{label(r.estado)}}</option>}</select></div>}
@if(current();as w){<section class="card"><div class="section-heading"><h2>{{label(w.estado)}}</h2><a [routerLink]="['/activity']" [queryParams]="{run:w.id}">Ver registro del coordinador</a></div>
<p class="muted tiny">{{short(w.solicitud.objetivo)}}</p>
@if(w.solicitud.objetivo.length>140){<details style="margin:8px 0"><summary class="text-button">Ver la solicitud completa</summary><p class="tiny">{{w.solicitud.objetivo}}</p></details>}
@if(w.estado!=='completado'){<div class="progress-card" role="status">@if(active()){<span class="spinner"></span>}<div><strong>Etapa {{stageProgress(w).current}} de {{stageProgress(w).total}} · {{stageProgress(w).label}}</strong><p class="muted tiny">Consulta el detalle de cada etapa si lo necesitas.</p></div></div>}
<details style="margin:10px 0"><summary class="text-button">Ver el detalle de cada etapa</summary>
<ol class="agent-progress">@for(s of stages;track s.id){<li [class.done]="w.pasos[s.id]?.completado" [class.failed]="w.resultado?.fase===s.id"><strong>{{s.label}}</strong>
@if(w.pasos[s.id];as step){<span class="muted">{{step.version?' · v'+step.version:''}} {{step.decision==='validado_automaticamente'?' · validado automáticamente':step.decision==='aprobado_por_humano'?' · aprobado por ti':''}}</span>
@if(step.ejecucion){ <a [routerLink]="['/activity']" [queryParams]="{run:step.ejecucion}">Ver agentes y verificaciones</a>}}
</li>}</ol>
</details>
@if(w.resultado?.mensaje){<div class="warning-banner" role="status">{{w.resultado.mensaje}} @if(w.resultado.enlace){<a [routerLink]="w.resultado.enlace" (click)="openConversation(w)">Abrir etapa para revisar</a>}</div>}
@if(w.estado==='completado'){<p>Producto generado y verificado. Puedes consultar el código, las pruebas y sus resultados.</p><a class="button primary" routerLink="/construction">Abrir producto final</a>}
<div class="mockup-actions">@if(active()){<button class="button secondary" [disabled]="busy()" (click)="pause()">Pausar y conservar avance</button>}@else if(w.estado!=='completado'){<button class="button primary" [disabled]="busy()" (click)="resume()">Continuar desde el avance guardado</button>}
<a class="button secondary" routerLink="/chat" (click)="openConversation(w)">Hablar con el analista de este flujo</a></div>
@if(w.estado==='error'||(w.estado==='esperando_revision'&&['backlog','mockups','arquitectura','construccion'].includes(w.resultado?.fase))){<p class="muted">Después de corregir la causa, puedes repetir solo esta etapa. Este nuevo intento utiliza la API y conserva el historial.</p><button class="button secondary" [disabled]="busy()" (click)="retry()">Generar otro intento de esta etapa</button>}
</section>}
}@else{<p>Selecciona o crea un proyecto para comenzar.</p>}</div>`})
export class Workflow implements OnDestroy {
 store=inject(Store); router=inject(Router); runs=signal<any[]>([]); current=signal<any>(null); selected=signal(''); busy=signal(false);
 objective=''; deployLocal=false; private timer?:ReturnType<typeof setTimeout>; private disposed=false;
 stages=[{id:'analisis',label:'Análisis del negocio y documentación'},{id:'requisitos',label:'Requisitos y línea base'},{id:'backlog',label:'Épicas, features e historias'},{id:'mockups',label:'Diseño funcional'},{id:'arquitectura',label:'Arquitectura y plan técnico'},{id:'construccion',label:'Código y pruebas reales'},{id:'despliegue',label:'Instancia local (si la solicitaste)'}];
 constructor(){effect(()=>{const pid=this.store.project()?.id_proyecto;clearTimeout(this.timer);this.runs.set([]);this.current.set(null);this.selected.set('');if(pid)void this.load(pid);});}
 ngOnDestroy(){this.disposed=true;clearTimeout(this.timer);}
 base(){return '/projects/'+this.store.project()?.id_proyecto+'/workflow';}
 active(){return ['pendiente','ejecutando'].includes(this.current()?.estado);}
 label(s:string){return ({pendiente:'En espera',ejecutando:'Desarrollo en curso',esperando_revision:'Necesita revisión',completado:'Producto verificado',error:'Ejecución detenida',interrumpido:'Pausado'} as Record<string,string>)[s]||s;}
 short(t:string,n=140){return t&&t.length>n?t.slice(0,n).trimEnd()+'…':t;}
 stageProgress(w:any){const idx=this.stages.findIndex(s=>!w.pasos[s.id]?.completado);const total=this.stages.length;if(idx===-1)return{current:total,total,label:'Todas las etapas completadas'};return{current:idx+1,total,label:this.stages[idx].label};}
 async load(pid:string){try{const rows=await this.store.api.request<any[]>('/projects/'+pid+'/workflow');if(pid!==this.store.project()?.id_proyecto||this.disposed)return;this.runs.set(rows);if(rows.length)await this.choose(this.selected()||rows[0].id);}catch(e){this.store.api.showError(e);}}
 async choose(id:string){clearTimeout(this.timer);this.selected.set(id);const pid=this.store.project()?.id_proyecto;try{const value=await this.store.api.request<any>(this.base()+'/'+id);if(pid!==this.store.project()?.id_proyecto||id!==this.selected()||this.disposed)return;this.current.set(value);if(this.active())this.timer=setTimeout(()=>void this.choose(id),2000);}catch(e){this.store.api.showError(e);}}
 async start(){this.busy.set(true);try{const r=await this.store.api.request<any>(this.base(),'POST',{id_solicitud:crypto.randomUUID(),objetivo:this.objective,desplegar_local:this.deployLocal});this.selected.set(r.id_ejecucion);await this.load(this.store.project()!.id_proyecto);const cid=this.current()?.id_conversacion;if(cid){this.store.openConversation(cid);void this.router.navigate(['/chat']);}}catch(e){this.store.api.showError(e);}finally{this.busy.set(false);}}
 async resume(){this.busy.set(true);try{await this.store.api.request(this.base()+'/'+this.selected()+'/resume','POST');await this.choose(this.selected());}catch(e){this.store.api.showError(e);}finally{this.busy.set(false);}}
 async pause(){this.busy.set(true);try{await this.store.api.request(this.base()+'/'+this.selected()+'/pause','POST');await this.choose(this.selected());}catch(e){this.store.api.showError(e);}finally{this.busy.set(false);}}
 async retry(){this.busy.set(true);try{await this.store.api.request(this.base()+'/'+this.selected()+'/retry','POST');await this.choose(this.selected());}catch(e){this.store.api.showError(e);}finally{this.busy.set(false);}}
 openConversation(w:any){void this.store.openConversation(w.id_conversacion);}
}
