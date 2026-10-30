import { Component, OnDestroy, computed, effect, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Store } from '../core/store';
import { Notifications } from '../core/notifications';

const AGENTS:Record<string,string>={desarrollador_datos:'Desarrollador de datos',desarrollador_backend:'Desarrollador backend',desarrollador_portal:'Desarrollador portal (empleado)',desarrollador_panel:'Desarrollador panel (aprobadores)',agente_pruebas:'Agente de pruebas',agente_iac:'Agente IaC',validador_artefactos:'Validador de artefactos',ejecucion:'Verificación en Docker',fase_5:'Orquestador',instancia:'Instancia local'};
const FLOW=['desarrollador_datos','desarrollador_backend','desarrollador_portal','desarrollador_panel','agente_pruebas','agente_iac','ejecucion','validador_artefactos'];
const TABS=[{id:'resumen',label:'Producto'},{id:'archivos',label:'Archivos'},{id:'api',label:'API y datos'},{id:'pruebas',label:'Pruebas'},{id:'entorno',label:'Instancia local'},{id:'validacion',label:'Validación y consumo'}];

@Component({standalone:true,imports:[CommonModule,FormsModule,RouterLink],template:`
<div class="page architecture-page">
<div class="page-heading"><div><div class="eyebrow">FASE 05 · CONSTRUCCIÓN</div><h1>De la arquitectura al producto.</h1><p class="muted">Red de agentes: datos, backend, frontend, pruebas e IaC. Valida lo creado y monta el entorno local.</p></div><a class="button secondary" routerLink="/architecture">Ver arquitectura</a></div>
@if(store.project()){
<section class="card mockup-generation"><h2>Construir el producto</h2>
@if(sources().length){
<label>Arquitectura aprobada<select [(ngModel)]="sourceVersion">@for(s of sources();track s.version){<option [ngValue]="s.version">Arquitectura v{{s.version}} · backlog v{{s.version_backlog}}</option>}</select></label>
<label>Indicaciones (opcional)<textarea [(ngModel)]="instructions" rows="2" maxlength="4000" placeholder="Por ejemplo: usar una paleta azul corporativa; incluir datos semilla de tres áreas."></textarea></label>
<p class="muted tiny">Los agentes escriben el código en paralelo donde es posible; el andamiaje, el balanceador y las reglas no usan modelo. Cada ciclo se verifica con Docker real y se corrige solo el agente responsable (máximo tres correcciones).</p>
<button class="button primary" [disabled]="busy()||!sourceVersion" (click)="generate()">{{busy()?'Construyendo y verificando…':'Construir producto'}}</button>
}@else{<p class="muted">Primero aprueba y publica una arquitectura en la fase 4.</p>}
@if(runId()){<ol class="agent-progress">@for(step of steps();track step.agent){<li [class.done]="step.state==='completado'" [class.failed]="step.state==='error'"><strong>{{step.label}}</strong> <span class="muted tiny">{{step.text}}</span></li>}</ol>
<p><a [routerLink]="['/activity']" [queryParams]="{run:runId()}">Ver ejecución y contratos entre agentes</a></p><p aria-live="polite" [class.validation-error]="progressFailed()" [class.muted]="!progressFailed()">{{progress()}}</p>}
</section>

<div class="section-heading"><h2>Productos y versiones <span class="count-label">{{versions().length}}</span></h2><select aria-label="Versión de construcción" [ngModel]="selectedVersion()" (ngModelChange)="loadVersion(+$event)"><option [ngValue]="0">Selecciona una versión</option>@for(r of versions();track r.version){<option [ngValue]="r.version">v{{r.version}} · arquitectura v{{r.version_arquitectura}} · {{r.decision==='validado_automaticamente'?'Validada automáticamente':r.decision==='aprobado_por_humano'?'Aprobada':r.decision==='descartado'?'Rechazada':'Pendiente'}}</option>}</select></div>

@if(content();as c){
<section class="card"><div class="section-heading"><div><h2>Producto v{{c.version_construccion}}</h2><p class="muted">Arquitectura v{{c.version_arquitectura_origen}} · Backlog v{{c.version_backlog_origen}} · {{c.fecha|date:'dd/MM/yyyy HH:mm'}}</p></div><span class="pill">{{c.validacion.puede_publicar?'Listo para montar':'Requiere corrección'}}</span></div>
<nav class="arch-tabs" role="tablist">@for(t of tabs;track t.id){<button role="tab" [class.selected]="tab()===t.id" [attr.aria-selected]="tab()===t.id" (click)="tab.set(t.id)">{{t.label}}</button>}</nav>
@switch(tab()){
@case('resumen'){
<div class="arch-stats"><div><strong>{{generatedCount()}}</strong><span>archivos de los agentes</span></div><div><strong>{{c.aplicaciones.length}}</strong><span>aplicaciones</span></div><div><strong>{{c.tablas.length}}</strong><span>tablas</span></div><div><strong>{{c.endpoints.length}}</strong><span>endpoints</span></div><div><strong>{{c.casos_prueba.length}}</strong><span>casos de prueba</span></div><div><strong>{{totalTokens()|number}}</strong><span>tokens usados</span></div></div>
<h3>Carpetas del proyecto</h3><div class="table-card"><table><tbody><tr><td><b>Aplicación</b></td><td><code>{{envelope()?.carpetas?.aplicacion}}</code></td></tr><tr><td><b>Entregables</b></td><td><code>{{envelope()?.carpetas?.entregables}}</code></td></tr></tbody></table></div>
<h3>Para el desarrollador</h3><ol class="dev-guide"><li>Abre la carpeta de la aplicación: <code>db/</code>, <code>backend/</code>, <code>frontend/</code> e <code>infra/terraform/</code>.</li><li>Pulsa <b>Montar entorno local</b> en la pestaña Entorno local, o ejecuta <code>docker compose up -d --build</code>.</li><li>Los entregables incluyen la arquitectura (README, drawio, k8s), el reporte de construcción y el resultado del entorno local.</li></ol>
}
@case('archivos'){<div class="code-browser"><aside><input [(ngModel)]="fileFilter" placeholder="Filtrar archivos" aria-label="Filtrar archivos"/>@for(f of fileList();track f.path){<button [class.selected]="filePath()===f.path" (click)="openFile(f.path)"><span>{{f.path}}</span><small class="muted">{{f.origin}}</small></button>}</aside>
<div class="file-preview">@if(filePath()){<div class="section-heading"><strong>{{filePath()}}</strong><button class="button secondary" (click)="download()">Descargar</button></div><pre>{{fileContent()}}</pre>}@else{<p class="muted">Selecciona un archivo para ver su contenido.</p>}</div></div>}
@case('api'){<h3>Endpoints</h3><div class="table-card"><table><thead><tr><th>Método</th><th>Ruta</th><th>Descripción</th><th>Historias</th></tr></thead><tbody>@for(e of c.endpoints;track $index){<tr><td><span class="pill">{{e.metodo}}</span></td><td><code>{{e.ruta}}</code></td><td>{{e.descripcion}}</td><td>{{e.ids_historias.join(', ')}}</td></tr>}</tbody></table></div>
<h3>Tablas</h3><div class="table-card"><table><thead><tr><th>Tabla</th><th>Columnas</th></tr></thead><tbody>@for(t of c.tablas;track t.nombre){<tr><td><b>{{t.nombre}}</b></td><td>{{t.columnas.join(', ')}}</td></tr>}</tbody></table></div>}
@case('pruebas'){<p class="muted">Cada caso está trazado a un criterio de aceptación. Se ejecutan con pytest dentro del contenedor al montar el entorno local.</p>
@if(envelope()?.entorno?.resultado?.pruebas){<p><b>Último resultado:</b> {{envelope()?.entorno?.resultado?.pruebas}}</p>}
<div class="table-card"><table><thead><tr><th>ID</th><th>Criterio</th><th>Archivo</th><th>Qué verifica</th></tr></thead><tbody>@for(t of c.casos_prueba;track t.id){<tr><td class="item-code">{{t.id}}</td><td>{{t.criterio}}</td><td><code>{{t.archivo}}</code></td><td>{{t.descripcion}}</td></tr>}</tbody></table></div>}
@case('entorno'){
<div class="deploy-panel"><div><h3>Entorno local con Docker</h3><p class="muted">Despliega cada componente en orden, como en una instancia EC2: base de datos, backend, aplicaciones, balanceador; luego verifica las respuestas y ejecuta las pruebas. Te avisaremos con una notificación al terminar.</p>
@if(envelope()?.entorno;as e){<p>Estado: <span class="pill" [class.sage]="e.estado==='completado'">{{stateLabel(e.estado)}}</span></p>
@if(e.resultado?.urls && e.estado!=='detenido'){<p><a class="button primary" [href]="e.resultado.urls.portal" target="_blank" rel="noopener">Abrir portal del empleado</a>@if(e.resultado.urls.panel){ <a class="button primary" [href]="e.resultado.urls.panel" target="_blank" rel="noopener">Abrir panel de aprobadores</a>} <a class="button secondary" [href]="e.resultado.urls.api" target="_blank" rel="noopener">Ver API</a></p><p class="muted tiny">El token del panel está en: <code>{{e.resultado.admin_env}}</code> (variable ADMIN_API_TOKEN).</p>}}
<div class="mockup-actions"><button class="button primary" [disabled]="deploying()||!c.validacion.puede_publicar||(envelope()?.decision!=='aprobado_por_humano'&&envelope()?.decision!=='validado_automaticamente')" (click)="deploy()">{{deploying()?'Desplegando instancia…':'Desplegar en instancia local'}}</button><button class="button secondary" [disabled]="deploying()||!envelope()?.entorno" (click)="stop()">Detener entorno</button></div>
@if(deployLog().length){<ol class="agent-progress">@for(l of deployLog();track $index){<li [class.done]="l.state==='completado'" [class.failed]="l.state==='error'"><strong>{{l.label}}</strong> <span class="muted tiny">{{l.text}}</span></li>}</ol>}
@for(p of envelope()?.entorno?.resultado?.pasos||[];track $index){<details><summary>{{p.paso}} · {{p.ok?'correcto':'falló'}}</summary><pre>{{p.detalle}}</pre></details>}
</div></div>}
@case('validacion'){<h3>Validación de artefactos</h3><p class="muted tiny">Reglas sin modelo: sintaxis Python y TypeScript, YAML, docker compose config, dependencias permitidas, rutas por agente y secretos. Después, revisión semántica.</p>
@for(f of c.validacion.observaciones;track $index){<p [class.validation-error]="f.severidad==='error'"><strong>{{f.severidad==='error'?'Bloqueo':'Advertencia'}} · {{agent(f.agente)}}:</strong> {{f.descripcion}} @if(f.archivo){<code>{{f.archivo}}</code>}</p>}@empty{<p class="muted">Sin observaciones.</p>}@if(!c.validacion.puede_publicar){<button class="button primary" [disabled]="busy()" (click)="autoFix(c)">{{busy()?'Corrigiendo…':'Corregir automáticamente'}}</button><p class="muted tiny">Vuelve a generar el producto pidiéndole al equipo que resuelva los bloqueos de arriba, sin que tengas que redactar instrucciones técnicas.</p>}
<p class="tiny muted">Correcciones automáticas: {{c.correcciones_automaticas}} / 3</p>
<h3>Consumo por agente</h3><div class="table-card"><table><thead><tr><th>Agente</th><th>Llamadas</th><th>Tokens entrada</th><th>Tokens salida</th><th>Tiempo</th></tr></thead><tbody>@for(row of usage();track row.agent){<tr><td>{{agent(row.agent)}}</td><td>{{row.llamadas}}</td><td>{{row.entrada|number}}</td><td>{{row.salida|number}}</td><td>{{(row.ms/1000)|number:'1.1-1'}} s</td></tr>}<tr><td><b>Total</b></td><td></td><td colspan="2"><b>{{totalTokens()|number}}</b></td><td></td></tr></tbody></table></div>
<p><a [routerLink]="['/activity']" [queryParams]="{run:c.id_ejecucion}">Trazabilidad de esta versión</a></p>}
}
</section>
<section class="card"><h3>Decisión de construcción</h3>@if(!envelope()?.decision){<label>Nota de revisión<textarea [(ngModel)]="reviewNote" rows="2" placeholder="Motivo de aprobación o rechazo"></textarea></label><div class="mockup-actions"><button class="button secondary" [disabled]="busy()||reviewNote.trim().length<3" (click)="review('rechazar')">Rechazar</button><button class="button primary" [disabled]="busy()||reviewNote.trim().length<3||!c.validacion.puede_publicar" (click)="review('aprobar')">Aprobar producto</button></div>}@else{<p>{{envelope()?.decision==='validado_automaticamente'?'Validado automáticamente. El despliegue empieza solo cuando pulses el botón.':'Nota registrada:'}} {{envelope()?.nota}}</p>}</section>
}@else{<section class="empty-card"><h3>Un producto trazable</h3><p>El código, las pruebas, la IaC y el entorno local aparecerán aquí.</p></section>}
}@else{<p>Selecciona un proyecto para comenzar.</p>}
</div>`})
export class Construction implements OnDestroy {
 store=inject(Store);notifications=inject(Notifications);tabs=TABS;
 sources=signal<any[]>([]);versions=signal<any[]>([]);envelope=signal<any>(null);content=signal<any>(null);selectedVersion=signal(0);
 busy=signal(false);deploying=signal(false);runId=signal('');progress=signal('');progressFailed=signal(false);tab=signal('resumen');filePath=signal('');fileContent=signal('');
 activity=signal<Record<string,{state:string;text:string}>>({});deployLog=signal<{label:string;state:string;text:string}[]>([]);
 sourceVersion=0;instructions='';reviewNote='';fileFilter='';private controller?:AbortController;
 steps=computed(()=>FLOW.map(agent=>({agent,label:AGENTS[agent],...(this.activity()[agent]||{state:'pendiente',text:'En espera'})})));
 usage=computed(()=>Object.entries(this.content()?.consumo||{}).map(([agent,v]:[string,any])=>({agent,...v})));
 totalTokens=computed(()=>this.usage().reduce((s,r)=>s+r.entrada+r.salida,0));
 generatedCount=computed(()=>Object.keys(this.content()?.archivos||{}).length);
 constructor(){effect(()=>{const id=this.store.project()?.id_proyecto;this.controller?.abort();this.sources.set([]);this.versions.set([]);this.envelope.set(null);this.content.set(null);this.runId.set('');this.busy.set(false);this.deploying.set(false);this.selectedVersion.set(0);if(id)void this.load(id);});}
 ngOnDestroy(){this.controller?.abort();}
 base(pid:string){return `/projects/${pid}/construction`;}
 agent(id:string){return AGENTS[id]||id;}
 stateLabel(s:string){return ({completado:'Funcionando',con_fallos:'Funcionando con pruebas fallidas',error:'Falló',detenido:'Detenido',interrumpido:'Interrumpido'} as any)[s]||s;}
  fileList(){const c=this.content();if(!c)return [];const q=this.fileFilter.toLowerCase();return Object.keys(c.archivos||{}).filter(p=>p.toLowerCase().includes(q)).sort().map(path=>({path,origin:path.startsWith('db/')?'datos':path.startsWith('backend/')?'backend':path.startsWith('portal/')?'portal':path.startsWith('panel/')?'panel':path.startsWith('infra/')?'IaC':'base'}));}
 async load(pid:string){try{const [arch,versions,runs]=await Promise.all([this.store.api.request<any[]>(`/projects/${pid}/architecture`),this.store.api.request<any[]>(this.base(pid)),this.store.api.request<any[]>(`/projects/${pid}/executions`)]);if(pid!==this.store.project()?.id_proyecto)return;this.sources.set(arch.filter(a=>['aprobado_por_humano','validado_automaticamente'].includes(a.decision)));this.sourceVersion=this.sources()[0]?.version||0;this.versions.set(versions);if(versions.length)await this.loadVersion(versions[0].version);const active=runs.find(r=>['construccion','despliegue'].includes(r.tipo)&&['pendiente','ejecutando'].includes(r.estado));if(active)void this.monitor(pid,active.id_ejecucion,active.tipo==='despliegue');}catch(e){this.store.api.showError(e);}}
 async loadVersion(version:number){const pid=this.store.project()?.id_proyecto;if(!pid||!version)return;try{const r=await this.store.api.request<any>(`${this.base(pid)}/${version}`);if(pid!==this.store.project()?.id_proyecto)return;this.envelope.set(r);this.content.set(r.payload);this.selectedVersion.set(version);this.filePath.set('');this.fileContent.set('');this.reviewNote='';}catch(e){this.store.api.showError(e);}}
 async openFile(path:string){const pid=this.store.project()?.id_proyecto;if(!pid)return;try{const f=await this.store.api.request<{contenido:string}>(`${this.base(pid)}/${this.selectedVersion()}/file?path=${encodeURIComponent(path)}`);this.filePath.set(path);this.fileContent.set(f.contenido);}catch(e){this.store.api.showError(e);}}
 download(){const url=URL.createObjectURL(new Blob([this.fileContent()],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=this.filePath().split('/').pop()||'archivo.txt';a.click();URL.revokeObjectURL(url);}
 async autoFix(c:any){
   const blocking=(c.validacion?.observaciones||[]).filter((f:any)=>f.severidad==='error');
   if(!blocking.length)return;
   this.sourceVersion=c.version_arquitectura_origen;
   this.instructions='Corrige los siguientes bloqueos detectados por la validación automática:\n'+blocking.map((f:any)=>`- ${this.agent(f.agente)}: ${f.descripcion}${f.archivo?` (${f.archivo})`:''}`).join('\n');
   await this.generate(true);
 }
 async generate(reuse=false){const pid=this.store.project()?.id_proyecto;if(!pid)return;this.busy.set(true);this.progressFailed.set(false);this.activity.set({});try{const r=await this.store.api.request<any>(`${this.base(pid)}/generate`,'POST',{version_arquitectura:this.sourceVersion,id_solicitud:crypto.randomUUID(),instrucciones:this.instructions,reutilizar_candidato:reuse});await this.monitor(pid,r.id_ejecucion,false);}catch(e){this.store.api.showError(e);}finally{if(pid===this.store.project()?.id_proyecto)this.busy.set(false);}}
 async deploy(){const pid=this.store.project()?.id_proyecto;if(!pid)return;this.deploying.set(true);this.deployLog.set([]);try{const r=await this.store.api.request<any>(`${this.base(pid)}/${this.selectedVersion()}/deploy`,'POST',{id_solicitud:crypto.randomUUID()});await this.monitor(pid,r.id_ejecucion,true);}catch(e){this.store.api.showError(e);}finally{if(pid===this.store.project()?.id_proyecto)this.deploying.set(false);}}
 async stop(){const pid=this.store.project()?.id_proyecto;if(!pid)return;this.deploying.set(true);try{await this.store.api.request(`${this.base(pid)}/${this.selectedVersion()}/stop`,'POST');await this.loadVersion(this.selectedVersion());}catch(e){this.store.api.showError(e);}finally{this.deploying.set(false);}}
 async monitor(pid:string,run:string,deployment:boolean){this.controller?.abort();const controller=new AbortController();this.controller=controller;
  if(deployment){this.deploying.set(true);this.tab.set('entorno');}else{this.runId.set(run);this.busy.set(true);}
  try{await this.store.api.events(`/projects/${pid}/executions/${run}/events`,(name,data)=>{if(pid!==this.store.project()?.id_proyecto||name!=='actividad')return;
     if(deployment){if(data.componente==='instancia')this.deployLog.update(l=>{const label=data.operacion.replaceAll('_',' ');const rest=l.filter(x=>x.label!==label);return [...rest,{label,state:data.estado,text:data.descripcion}];});return;}
     this.progress.set(data.descripcion||'Trabajando…');
     if(AGENTS[data.componente]){const tokens=data.datos?.consumo?` · ${(data.datos.consumo.entrada||0)+(data.datos.consumo.salida||0)} tokens`:'';this.activity.update(a=>({...a,[data.componente]:{state:data.estado,text:(data.descripcion||'')+tokens}}));}},controller.signal);
   if(controller.signal.aborted||pid!==this.store.project()?.id_proyecto)return;
   const rows=await this.store.api.request<any[]>(this.base(pid));this.versions.set(rows);
   if(!deployment){const result=await this.store.api.request<any>(`/projects/${pid}/executions/${run}`);const failed=result.estado!=='completado';this.progressFailed.set(failed);this.progress.set(failed?(result.resultado?.error||'La ejecución se detuvo.'):'Producto construido. Revísalo y monta el entorno local.');if(rows.length)await this.loadVersion(rows[0].version);}
   else await this.loadVersion(this.selectedVersion());
   void this.notifications.refresh();}
  catch(e){if(!controller.signal.aborted)this.store.api.showError(e);}finally{if(this.controller===controller){this.busy.set(false);this.deploying.set(false);}}}
 async review(action:string){const pid=this.store.project()?.id_proyecto;if(!pid)return;this.busy.set(true);try{this.envelope.set(await this.store.api.request<any>(`${this.base(pid)}/${this.selectedVersion()}/review`,'POST',{accion:action,nota:this.reviewNote}));this.versions.set(await this.store.api.request<any[]>(this.base(pid)));}catch(e){this.store.api.showError(e);}finally{this.busy.set(false);}}
}
