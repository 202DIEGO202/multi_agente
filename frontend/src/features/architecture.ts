import { Component, OnDestroy, computed, effect, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Store } from '../core/store';
import { JsonViewer } from '../shared/json-viewer';
import { Diagram, DiagramView } from '../shared/diagram';

const AGENTS:Record<string,string>={arquitecto_software:'Arquitecto de software',arquitecto_infraestructura:'Arquitecto de infraestructura',validador_arquitectura:'Validador',planificador:'Planificador',validacion_estructural:'Reglas deterministas',fase_4:'Orquestador'};
const TABS=[
 {id:'resumen',label:'Resumen'},{id:'calidad',label:'Atributos de calidad'},{id:'decisiones',label:'Decisiones y tradeoffs'},
 {id:'c4',label:'C4'},{id:'infra',label:'Infraestructura'},{id:'flujos',label:'Secuencias y flujos'},
 {id:'plan',label:'Plan técnico'},{id:'archivos',label:'Archivos'},{id:'consumo',label:'Validación y consumo'}];

@Component({standalone:true,imports:[CommonModule,FormsModule,RouterLink,JsonViewer,Diagram],template:`
<div class="page architecture-page">
<div class="page-heading"><div><div class="eyebrow">FASE 04 · ARQUITECTURA</div><h1>De las historias al diseño técnico.</h1><p class="muted">Arquitecto de software, arquitecto de infraestructura, validador y planificador. Ejecutable en local y en la nube.</p></div><a class="button secondary" routerLink="/mockups">Ver diseño funcional</a></div>
@if(store.project()){
<section class="card mockup-generation"><h2>Preparar la arquitectura</h2>
@if(sources().length){
<label>Backlog publicado<select [(ngModel)]="sourceVersion"><option [ngValue]="0">Selecciona una versión</option>@for(s of sources();track s.version){<option [ngValue]="s.version">Backlog v{{s.version}} · línea base v{{s.version_linea_base}}</option>}</select></label>
<label>Indicaciones (opcional)<textarea [(ngModel)]="instructions" rows="2" maxlength="4000" placeholder="Por ejemplo: priorizar disponibilidad; el correo se envía por SMTP corporativo."></textarea></label>
<div><span class="muted tiny">Tecnologías permitidas:</span><div class="chip-row">@for(t of technologies();track t){<span class="pill">{{t}}</span>}</div></div>
<p class="muted tiny">Usa Azure en 4 agentes (software, infraestructura, validador, planificador). Las reglas, los diagramas y los archivos se generan sin modelo. Máximo una corrección dirigida.</p>
<button class="button primary" [disabled]="busy()||!sourceVersion" (click)="generate()">{{busy()?'Arquitectura en curso…':'Generar arquitectura'}}</button>
}@else{<p class="muted">Primero aprueba y publica un backlog. Si hay mockups aprobados de ese backlog, también se usan.</p>}
@if(runId()){<ol class="agent-progress">@for(step of steps();track step.agent){<li [class.done]="step.state==='completado'" [class.failed]="step.state==='error'"><strong>{{step.label}}</strong> <span class="muted tiny">{{step.text}}</span></li>}</ol>
<p><a [routerLink]="['/activity']" [queryParams]="{run:runId()}">Ver ejecución y contratos entre agentes</a></p><p aria-live="polite" class="muted">{{progress()}}</p>}
</section>

<div class="section-heading"><h2>Arquitecturas y versiones <span class="count-label">{{versions().length}}</span></h2><select aria-label="Versión de arquitectura" [ngModel]="selectedVersion()" (ngModelChange)="loadVersion(+$event)"><option [ngValue]="0">Selecciona una revisión</option>@for(r of versions();track r.version){<option [ngValue]="r.version">v{{r.version}} · {{r.decision==='validado_automaticamente'?'Validada automáticamente':r.decision==='aprobado_por_humano'?'Aprobada':r.decision==='descartado'?'Rechazada':'Pendiente de revisión'}}</option>}</select></div>

@if(content();as c){
@if(envelope()?.desactualizado){<div class="warning-banner">El backlog de origen cambió. Genera una nueva arquitectura antes de aprobar.</div>}
<section class="card"><div class="section-heading"><div><h2>Arquitectura v{{c.version_arquitectura}}</h2><p class="muted">Backlog v{{c.version_backlog_origen}} · Línea base v{{c.version_linea_base_origen}}{{c.version_mockups_origen?' · Mockups v'+c.version_mockups_origen:''}} · {{c.fecha|date:'dd/MM/yyyy HH:mm'}}</p></div><span class="pill">{{envelope()?.decision==='validado_automaticamente'?'Validada automáticamente':envelope()?.decision==='aprobado_por_humano'?'Aprobada':envelope()?.decision==='descartado'?'Rechazada':c.validacion.puede_publicar?'Lista para revisar':'Requiere corrección'}}</span></div>
<nav class="arch-tabs" role="tablist">@for(t of tabs;track t.id){<button role="tab" [class.selected]="tab()===t.id" [attr.aria-selected]="tab()===t.id" (click)="tab.set(t.id)">{{t.label}}</button>}</nav>

@switch(tab()){
@case('resumen'){
<div class="arch-grid"><div><h3>Cómo está construida</h3><p>{{c.software.resumen}}</p><p><span class="pill">{{c.software.estilo.replaceAll('_',' ')}}</span></p></div><div><h3>Dónde y cómo funciona</h3><p>{{c.infraestructura.resumen}}</p></div></div>
<div class="arch-stats"><div><strong>{{c.software.atributos_calidad.length}}</strong><span>atributos de calidad</span></div><div><strong>{{c.software.decisiones.length}}</strong><span>decisiones (ADR)</span></div><div><strong>{{c.software.contenedores.length}}</strong><span>contenedores</span></div><div><strong>{{c.software.componentes.length}}</strong><span>componentes</span></div><div><strong>{{c.plan?.tareas?.length||0}}</strong><span>tareas técnicas</span></div><div><strong>{{totalTokens()|number}}</strong><span>tokens usados</span></div></div>
<h3>Para el desarrollador</h3><ol class="dev-guide"><li>Revisa los <b>atributos de calidad</b>: son las metas medibles que el diseño debe cumplir.</li><li>Lee las <b>decisiones</b>: explican por qué se eligió cada opción y qué se sacrifica.</li><li>Usa el <b>C4</b> para ubicar tu módulo y sus dependencias.</li><li>En <b>Archivos</b> descarga <code>docker-compose.yml</code> para correr todo en local y <code>k8s.yaml</code> para EKS.</li><li>Toma tus tareas del <b>Plan técnico</b> en el orden indicado.</li></ol>
}
@case('calidad'){<div class="table-card"><table><thead><tr><th>ID</th><th>Atributo</th><th>Escenario</th><th>Medida</th><th>Prioridad</th><th>Origen</th></tr></thead><tbody>@for(a of c.software.atributos_calidad;track a.id){<tr><td class="item-code">{{a.id}}</td><td>{{a.atributo}}</td><td>{{a.escenario}}</td><td><b>{{a.medida}}</b></td><td><span class="pill">{{a.prioridad}}</span></td><td>{{a.ids_requisitos.join(', ')}}</td></tr>}</tbody></table></div>}
@case('decisiones'){@for(d of c.software.decisiones;track d.id){<article class="adr"><h3><span class="item-code">{{d.id}}</span> {{d.titulo}}</h3><p><b>Contexto:</b> {{d.contexto}}</p><p><b>Decisión:</b> {{d.decision}}</p><p><b>Alternativas consideradas:</b> {{d.alternativas.join('; ')}}</p><div class="tradeoff"><div><h4>A favor</h4><ul>@for(v of d.ventajas;track $index){<li>{{v}}</li>}</ul></div><div><h4>En contra (tradeoff)</h4><ul>@for(v of d.desventajas;track $index){<li>{{v}}</li>}</ul></div></div><p class="muted tiny">Atributos: {{d.ids_atributos.join(', ')}}</p></article>}}
@case('c4'){@for(v of viewsBy('c4-');track v.id){<ng-container *ngTemplateOutlet="diagramCard;context:{$implicit:v}"/>}
<h3>Componentes</h3><div class="table-card"><table><thead><tr><th>ID</th><th>Componente</th><th>Contenedor</th><th>Responsabilidad</th><th>Historias</th><th>Operaciones</th></tr></thead><tbody>@for(m of c.software.componentes;track m.id){<tr><td class="item-code">{{m.id}}</td><td>{{m.nombre}}</td><td>{{m.contenedor}}</td><td>{{m.responsabilidad}}</td><td>{{m.ids_historias.join(', ')}}</td><td>{{m.operaciones.join('; ')}}</td></tr>}</tbody></table></div>}
@case('infra'){<div class="arch-grid"><div><h3>Estrategia de despliegue</h3><p>{{c.infraestructura.estrategia_despliegue}}</p></div><div><h3>Seguridad</h3><p>{{c.infraestructura.seguridad}}</p><h3>Observabilidad</h3><p>{{c.infraestructura.observabilidad}}</p></div></div>
@for(v of viewsBy('despliegue-');track v.id){<ng-container *ngTemplateOutlet="diagramCard;context:{$implicit:v}"/>}
<div class="table-card"><table><thead><tr><th>Nodo</th><th>Entorno</th><th>Tecnología</th><th>Aloja</th><th>Puerto</th><th>Réplicas</th><th>Variables</th><th>Explicación</th></tr></thead><tbody>@for(n of c.infraestructura.nodos;track n.id){<tr><td><span class="item-code">{{n.id}}</span> {{n.nombre}}</td><td><span class="pill">{{n.entorno}}</span></td><td>{{n.tecnologia}}</td><td>{{n.aloja.join(', ')}}</td><td>{{n.puerto||'—'}}</td><td>{{n.replicas}}</td><td>{{n.configuracion.join(', ')}}</td><td>{{n.explicacion}}</td></tr>}</tbody></table></div>}
@case('flujos'){@for(v of flowViews();track v.id){<ng-container *ngTemplateOutlet="diagramCard;context:{$implicit:v}"/>}}
@case('plan'){@if(c.plan){<p>{{c.plan.resumen}}</p><div class="table-card"><table><thead><tr><th>#</th><th>Tarea</th><th>Rol</th><th>Componentes</th><th>Historias</th><th>Depende de</th><th>Terminado cuando</th><th>Esfuerzo</th></tr></thead><tbody>@for(t of c.plan.tareas;track t.id;let i=$index){<tr><td>{{i+1}}</td><td><span class="item-code">{{t.id}}</span> <b>{{t.titulo}}</b><small class="muted">{{t.descripcion}}</small></td><td><span class="pill">{{t.rol}}</span></td><td>{{t.ids_componentes.join(', ')}}</td><td>{{t.ids_historias.join(', ')}}</td><td>{{t.depende_de.join(', ')||'—'}}</td><td><ul>@for(x of t.criterios_terminado;track $index){<li>{{x}}</li>}</ul></td><td>{{t.esfuerzo}}</td></tr>}</tbody></table></div>}@else{<p class="muted">No se planificó porque quedaron errores de arquitectura. Corrígelos y vuelve a generar.</p>}}
@case('archivos'){<p class="muted">Generados por código desde la arquitectura: siempre coinciden con lo que ves en pantalla.</p><div class="file-list">@for(f of fileNames;track f){<button class="button secondary" [class.selected]="fileName()===f" (click)="openFile(f)">{{f}}</button>}</div>
@if(fileContent()){<div class="file-preview"><div class="section-heading"><strong>{{fileName()}}</strong><button class="button primary" (click)="download()">Descargar</button></div><pre>{{fileContent()}}</pre></div>}}
@case('consumo'){<h3>Validación</h3>@for(f of c.validacion.observaciones;track $index){<p [class.validation-error]="f.severidad==='error'"><strong>{{f.severidad==='error'?'Bloqueo':'Advertencia'}} · {{agent(f.agente)}}:</strong> {{f.descripcion}} <span class="muted">{{f.ids_elementos.join(', ')}}</span></p>}@empty{<p class="muted">Sin observaciones de validación.</p>}
<p class="tiny muted">Correcciones automáticas: {{c.correcciones_automaticas}} / 1</p>
<h3>Consumo por agente</h3><div class="table-card"><table><thead><tr><th>Agente</th><th>Llamadas</th><th>Tokens entrada</th><th>Tokens salida</th><th>Tiempo</th></tr></thead><tbody>@for(row of usage();track row.agent){<tr><td>{{agent(row.agent)}}</td><td>{{row.llamadas}}</td><td>{{row.entrada|number}}</td><td>{{row.salida|number}}</td><td>{{(row.ms/1000)|number:'1.1-1'}} s</td></tr>}<tr><td><b>Total</b></td><td></td><td colspan="2"><b>{{totalTokens()|number}}</b></td><td><b>{{(totalMs()/1000)|number:'1.1-1'}} s</b></td></tr></tbody></table></div>
<div class="mockup-actions"><button class="button secondary" (click)="showJson.set(!showJson())">{{showJson()?'Cerrar JSON':'Ver modelo canónico (JSON)'}}</button><a class="button secondary" [routerLink]="['/activity']" [queryParams]="{run:c.id_ejecucion}">Trazabilidad de esta versión</a></div>@if(showJson()){<json-viewer [value]="c"/>}}
}
</section>
<section class="card"><h3>Decisión humana</h3>
@if(!envelope()?.decision){<label>Nota de revisión<textarea [(ngModel)]="reviewNote" rows="2" placeholder="Motivo de aprobación o rechazo"></textarea></label><div class="mockup-actions"><button class="button secondary" [disabled]="busy()||reviewNote.trim().length<3" (click)="review('rechazar')">Rechazar con observaciones</button><button class="button primary" [disabled]="busy()||reviewNote.trim().length<3||!c.validacion.puede_publicar||envelope()?.desactualizado||selectedVersion()!==versions()[0]?.version" (click)="review('aprobar')">Aprobar y publicar</button></div>}
@else{<p>Nota registrada: {{envelope()?.nota}}</p>}</section>
}@else{<section class="empty-card"><h3>Una arquitectura trazable</h3><p>Los atributos de calidad, decisiones, diagramas C4, infraestructura y plan técnico aparecerán aquí.</p></section>}
}@else{<p>Selecciona un proyecto para comenzar.</p>}
</div>
<ng-template #diagramCard let-v><article class="diagram-card"><div class="section-heading"><div><h3>{{v.titulo}}</h3><p class="muted tiny">{{v.explicacion}}</p></div><button class="text-button" (click)="toggleMermaid(v.id)">{{mermaidOpen()===v.id?'Ocultar Mermaid':'Ver Mermaid'}}</button></div><div class="diagram-scroll"><ui-diagram [view]="v"/></div>@if(mermaidOpen()===v.id){<pre>{{v.mermaid}}</pre>}</article></ng-template>`})
export class Architecture implements OnDestroy {
 store=inject(Store);tabs=TABS;fileNames=['README.md','docker-compose.yml','.env.example','k8s.yaml','arquitectura.drawio','arquitectura.json'];
 sources=signal<any[]>([]);versions=signal<any[]>([]);technologies=signal<string[]>([]);envelope=signal<any>(null);content=signal<any>(null);selectedVersion=signal(0);
 busy=signal(false);runId=signal('');progress=signal('');showJson=signal(false);tab=signal('resumen');mermaidOpen=signal('');fileName=signal('');fileContent=signal('');
 activity=signal<Record<string,{state:string;text:string}>>({});
 sourceVersion=0;instructions='';reviewNote='';private controller?:AbortController;
 steps=computed(()=>['arquitecto_software','arquitecto_infraestructura','validacion_estructural','validador_arquitectura','planificador'].map(agent=>({agent,label:AGENTS[agent],...(this.activity()[agent]||{state:'pendiente',text:'En espera'})})));
 usage=computed(()=>Object.entries(this.content()?.consumo||{}).map(([agent,v]:[string,any])=>({agent,...v})));
 totalTokens=computed(()=>this.usage().reduce((s,r)=>s+r.entrada+r.salida,0));
 totalMs=computed(()=>this.usage().reduce((s,r)=>s+r.ms,0));
 flowViews=computed(()=>(this.content()?.vistas||[]).filter((v:DiagramView)=>v.id.startsWith('sq-')||v.id.startsWith('flujo-')));
 constructor(){effect(()=>{const id=this.store.project()?.id_proyecto;this.controller?.abort();this.sources.set([]);this.versions.set([]);this.envelope.set(null);this.content.set(null);this.runId.set('');this.busy.set(false);this.selectedVersion.set(0);this.sourceVersion=0;if(id)void this.load(id);});}
 ngOnDestroy(){this.controller?.abort();}
 base(pid:string){return `/projects/${pid}/architecture`;}
 agent(id:string){return AGENTS[id]||id;}
 viewsBy(prefix:string):DiagramView[]{return (this.content()?.vistas||[]).filter((v:DiagramView)=>v.id.startsWith(prefix));}
 toggleMermaid(id:string){this.mermaidOpen.set(this.mermaidOpen()===id?'':id);}
 async load(pid:string){try{const [sources,versions,runs,tech]=await Promise.all([this.store.api.request<any[]>(`/projects/${pid}/backlog`),this.store.api.request<any[]>(this.base(pid)),this.store.api.request<any[]>(`/projects/${pid}/executions`),this.store.api.request<string[]>(`${this.base(pid)}/technologies`)]);if(pid!==this.store.project()?.id_proyecto)return;this.sources.set(sources.filter(s=>['aprobado_por_humano','validado_automaticamente'].includes(s.estado)));this.versions.set(versions);this.technologies.set(tech);this.sourceVersion=this.sources()[0]?.version||0;if(versions.length)await this.loadVersion(versions[0].version);const active=runs.find(r=>r.tipo==='arquitectura'&&['pendiente','ejecutando'].includes(r.estado));if(active)void this.monitor(pid,active.id_ejecucion);}catch(e){this.store.api.showError(e);}}
 async loadVersion(version:number){const pid=this.store.project()?.id_proyecto;if(!pid||!version)return;try{const result=await this.store.api.request<any>(`${this.base(pid)}/${version}`);if(pid!==this.store.project()?.id_proyecto)return;this.envelope.set(result);this.content.set(result.payload);this.selectedVersion.set(version);this.reviewNote='';this.showJson.set(false);this.fileName.set('');this.fileContent.set('');}catch(e){this.store.api.showError(e);}}
 async openFile(name:string){const pid=this.store.project()?.id_proyecto;if(!pid)return;try{const file=await this.store.api.request<{contenido:string}>(`${this.base(pid)}/${this.selectedVersion()}/files/${encodeURIComponent(name)}`);this.fileName.set(name);this.fileContent.set(file.contenido);}catch(e){this.store.api.showError(e);}}
 download(){const url=URL.createObjectURL(new Blob([this.fileContent()],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=this.fileName();a.click();URL.revokeObjectURL(url);}
 async generate(){const pid=this.store.project()?.id_proyecto;if(!pid)return;this.busy.set(true);this.activity.set({});try{const result=await this.store.api.request<any>(`${this.base(pid)}/generate`,'POST',{version_backlog:this.sourceVersion,id_solicitud:crypto.randomUUID(),instrucciones:this.instructions});if(pid!==this.store.project()?.id_proyecto)return;await this.monitor(pid,result.id_ejecucion);}catch(e){this.store.api.showError(e);}finally{if(pid===this.store.project()?.id_proyecto)this.busy.set(false);}}
 async monitor(pid:string,run:string){this.controller?.abort();const controller=new AbortController();this.controller=controller;this.runId.set(run);this.busy.set(true);
  try{await this.store.api.events(`/projects/${pid}/executions/${run}/events`,(name,data)=>{if(pid!==this.store.project()?.id_proyecto||name!=='actividad')return;this.progress.set(data.descripcion||'Trabajando…');
    if(AGENTS[data.componente]){const tokens=data.datos?.consumo?` · ${(data.datos.consumo.entrada||0)+(data.datos.consumo.salida||0)} tokens`:'';this.activity.update(a=>({...a,[data.componente]:{state:data.estado,text:(data.descripcion||'')+tokens}}));}},controller.signal);
   if(controller.signal.aborted||pid!==this.store.project()?.id_proyecto)return;
   const [rows,result]=await Promise.all([this.store.api.request<any[]>(this.base(pid)),this.store.api.request<any>(`/projects/${pid}/executions/${run}`)]);if(pid!==this.store.project()?.id_proyecto)return;this.versions.set(rows);
   if(result.estado==='error'||result.estado==='interrumpido'){this.progress.set(result.resultado?.error||'La ejecución se detuvo. Puedes reanudarla desde Actividad de IA.');return;}
   this.progress.set('Arquitectura guardada. Revisa cada pestaña antes de aprobar.');if(rows.length)await this.loadVersion(rows[0].version);}
  catch(e){if(!controller.signal.aborted)this.store.api.showError(e);}finally{if(this.controller===controller)this.busy.set(false);}}
 async review(action:string){const pid=this.store.project()?.id_proyecto;if(!pid)return;this.busy.set(true);try{const result=await this.store.api.request<any>(`${this.base(pid)}/${this.selectedVersion()}/review`,'POST',{accion:action,nota:this.reviewNote});if(pid!==this.store.project()?.id_proyecto)return;this.envelope.set(result);this.versions.set(await this.store.api.request<any[]>(this.base(pid)));}catch(e){this.store.api.showError(e);}finally{if(pid===this.store.project()?.id_proyecto)this.busy.set(false);}}
}
