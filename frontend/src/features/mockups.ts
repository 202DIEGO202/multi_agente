import { Component, effect, inject, signal, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Store } from '../core/store';
import { JsonViewer } from '../shared/json-viewer';

interface Control {clave:string;tipo:string;etiqueta:string;ayuda:string;obligatorio:boolean;opciones:string[];destino:string|null;ids_criterios:string[];}
interface Screen {id:string;version:number;titulo:string;descripcion:string;ids_historias:string[];ids_criterios_visuales?:string[];controles:Control[];}

@Component({standalone:true,imports:[CommonModule,FormsModule,RouterLink,JsonViewer],template:`
<div class="page mockup-page">
<div class="page-heading"><div><div class="eyebrow">FASE 03 · DISEÑO DE INTERFACES</div><h1>De las historias a las pantallas.</h1><p class="muted">Diseño, revisión y una corrección automática como máximo. Cada paso conserva su registro.</p></div><a class="button secondary" routerLink="/backlog">Ver backlog</a></div>
@if(store.project()){
<section class="card mockup-generation"><h2>Preparar un diseño</h2>
@if(sources().length){<label>Backlog publicado<select [(ngModel)]="sourceVersion"><option [ngValue]="0">Selecciona una versión</option>@for(source of sources();track source.version){<option [ngValue]="source.version">Backlog v{{source.version}} · {{source.estado}}</option>}</select></label>
<label>Indicaciones de diseño o cambios<textarea [(ngModel)]="instructions" rows="2" maxlength="4000" placeholder="Por ejemplo: mantener el estilo cálido y simplificar la pantalla inicial."></textarea></label>
<label>Alcance<select [(ngModel)]="target"><option value="">Diseño completo</option>@for(screen of content()?.diseno?.pantallas||[];track screen.id){<option [value]="screen.id">Solo {{screen.id}} · {{screen.titulo}}</option>}</select></label>
<p class="muted tiny">Generar usa Azure: diseñador + validador. Si hay bloqueos, se permite una corrección y otra validación. Consultar y aprobar no usa el modelo.</p>
<button class="button primary" [disabled]="busy()||!sourceVersion" (click)="generate()">{{busy()?'Diseño en curso…':target?'Refinar pantalla':'Generar mockups'}}</button>
}@else{<p class="muted">Primero aprueba y publica un backlog funcional. Después podrás generar sus pantallas.</p>}
@if(runId()){<p><a [routerLink]="['/activity']" [queryParams]="{run:runId()}">Ver ejecución y registros de los agentes</a></p><p aria-live="polite" class="muted">{{progress()}}</p>}
</section>
<div class="section-heading"><h2>Diseños y versiones <span class="count-label">{{versions().length}}</span></h2><select aria-label="Versión de mockups" [ngModel]="selectedVersion()" (ngModelChange)="loadVersion(+$event)"><option [ngValue]="0">Selecciona una revisión</option>@for(row of versions();track row.version){<option [ngValue]="row.version">v{{row.version}} · {{row.decision||'Pendiente de revisión'}}</option>}</select></div>
@if(content();as c){
@if(envelope()?.desactualizado){<div class="warning-banner">El origen cambió o tiene conflictos. Publica un backlog vigente y genera otra revisión antes de aprobar.</div>}
<section class="card"><div class="section-heading"><div><h2>Mockups v{{c.version_mockup}}</h2><p class="muted">Backlog v{{c.version_backlog_origen}} · Línea base v{{c.version_linea_base_origen}} · {{c.fecha|date:'dd/MM/yyyy HH:mm'}}</p></div><span class="pill">{{envelope()?.decision==='validado_automaticamente'?'Validado automáticamente':envelope()?.decision==='aprobado_por_humano'?'Aprobado y publicado':envelope()?.decision==='descartado'?'Rechazado':c.validacion.puede_publicar?'Listo para revisar':c.diseno.preguntas.length?'Necesita tu decisión':'Diseño pendiente de corrección'}}</span></div>
@if(c.validacion.revision_tecnica){<p class="muted">Referencias reparadas sin llamadas al modelo. Se conserva la revisión semántica anterior y sus advertencias.</p>}<p class="muted">Validación de estructura, cobertura y contraste. El agente no inspecciona una imagen del resultado.</p>
@for(finding of c.validacion.observaciones;track $index){<p [class.validation-error]="finding.severidad==='error'"><strong>{{finding.severidad==='error'?'Bloqueo':'Advertencia'}}:</strong> {{finding.descripcion}} {{finding.ids_elementos.join(', ')}}</p>}
@for(question of c.diseno.preguntas;track $index){<p class="validation-error">{{question}}</p>}
@if(!c.validacion.observaciones.length){<p class="muted">Sin observaciones de validación.</p>}
@if(c.diseno.criterios_no_visuales?.length){<details><summary>Criterios internos que se verificarán en el código y las pruebas</summary>@for(item of c.diseno.criterios_no_visuales;track item.id_criterio){<p><strong>{{item.id_criterio}}</strong>: {{item.justificacion}}</p>}</details>}
<p class="tiny muted">Correcciones automáticas realizadas: {{c.correcciones_automaticas}} / 1</p>
<div class="mockup-actions"><button class="button secondary" (click)="showJson.set(!showJson())">{{showJson()?'Cerrar JSON':'Ver contrato e historial de esta revisión'}}</button><a class="button secondary" [routerLink]="['/activity']" [queryParams]="{run:c.id_ejecucion}">Trazabilidad de esta versión</a></div>
@if(showJson()){<json-viewer [value]="c"/>}
</section>
<div class="mockup-workspace"><aside class="card mockup-screens"><h3>Pantallas</h3>@for(s of c.diseno.pantallas;track s.id){<button class="mockup-screen-link" [class.selected]="screenId()===s.id" (click)="chooseScreen(s.id)"><strong>{{s.id}} · v{{s.version}}</strong><span>{{s.titulo}}</span></button>}</aside>
<section class="card mockup-preview-shell"><div class="section-heading"><h3>Vista del prototipo</h3><div class="mockup-view-options"><label class="mockup-annotations-toggle"><input type="checkbox" role="switch" [checked]="showAnnotations()" (change)="toggleAnnotations()"/>Mostrar aclaraciones</label><select aria-label="Tamaño de la vista" [(ngModel)]="viewport"><option value="desktop">Escritorio</option><option value="mobile">Móvil</option></select></div></div><p class="muted tiny">Simulación: no envía SMS, correos ni datos. Usa valores de prueba.</p>
@if(screen();as s){
<div class="mockup-browser" [class.mockup-mobile]="viewport==='mobile'" [style.background]="c.diseno.paleta.fondo" [style.color]="c.diseno.paleta.texto">
<div class="mockup-browser-bar"><span>● ● ●</span><span>{{s.id}} · Prototipo</span></div>
<div class="mockup-canvas"><div class="mockup-form" [style.background]="c.diseno.paleta.superficie"><h2>{{s.titulo}}</h2>@if(showAnnotations()){<p class="mockup-explanation">{{s.descripcion}}</p>}
@for(control of s.controles;track control.clave){
@if(showAnnotations()||!isExplanatory(control)){
@switch(control.tipo){
@case('texto'){<p>{{control.etiqueta}}</p>}
@case('aviso'){<div class="mockup-notice" role="note">{{control.etiqueta}}</div>}
@case('ficha'){<section class="mockup-sheet" [attr.aria-label]="control.etiqueta"><h3>{{control.etiqueta}}</h3><dl>@for(row of control.opciones;track $index){<div><dt>{{fieldName(row)}}</dt><dd>{{fieldValue(row)}}</dd></div>}</dl></section>}
@case('entrada'){<label [for]="s.id+'-'+control.clave">{{control.etiqueta}}{{control.obligatorio?' *':''}}</label><input [id]="s.id+'-'+control.clave" [attr.aria-describedby]="showAnnotations()&&control.ayuda?s.id+'-'+control.clave+'-help':null" [required]="control.obligatorio" autocomplete="off" placeholder="Valor de prueba"/>}
@case('selector'){<label [for]="s.id+'-'+control.clave">{{control.etiqueta}}{{control.obligatorio?' *':''}}</label><select [id]="s.id+'-'+control.clave" [required]="control.obligatorio"><option value="">Selecciona una opción</option>@for(option of control.opciones;track $index){<option>{{option}}</option>}</select>}
@case('casilla'){<label class="mockup-check"><input type="checkbox" [required]="control.obligatorio"/> {{control.etiqueta}}</label>}
@case('boton'){<button type="button" class="mockup-cta" [style.background]="c.diseno.paleta.acento" [style.color]="c.diseno.paleta.texto_boton" (click)="simulate(control)">{{control.etiqueta}}</button>}
}
@if(showAnnotations()&&control.ayuda){<small [id]="s.id+'-'+control.clave+'-help'">{{control.ayuda}}</small>}
}
}
@if(simulation()){<p role="status" class="mockup-notice">{{simulation()}}</p>}
</div></div></div>
@if(showAnnotations()){<div class="mockup-trace"><strong>{{s.id}} · v{{s.version}}</strong><p>Historias: {{s.ids_historias.join(', ')}}</p><p>Criterios representados: {{criteria(s)}}</p>@if(s.ids_criterios_visuales?.length){<p>Criterios del estilo de pantalla: {{s.ids_criterios_visuales?.join(", ")}}</p>}</div>}
}
</section></div>
<section class="card"><h3>Cambios de esta revisión</h3>@if(c.cambios.paleta_modificada){<p>La paleta global cambió; todas las pantallas tienen una nueva versión.</p>}<p>Creadas: {{c.cambios.creadas.join(', ')||'Ninguna'}} · Modificadas: {{c.cambios.modificadas.join(', ')||'Ninguna'}} · Retiradas: {{c.cambios.retiradas.join(', ')||'Ninguna'}}</p>
@if(!envelope()?.decision){<label>Nota de revisión<textarea [(ngModel)]="reviewNote" rows="2" placeholder="Motivo de aprobación o rechazo" minlength="3"></textarea></label><div class="mockup-actions"><button class="button secondary" [disabled]="busy()||reviewNote.trim().length<3" (click)="review('rechazar')">Rechazar con observaciones</button><button class="button primary" [disabled]="busy()||reviewNote.trim().length<3||!c.validacion.puede_publicar||envelope()?.desactualizado||selectedVersion()!==versions()[0]?.version" (click)="review('aprobar')">Aprobar y publicar</button></div>}@else{<p>Nota registrada: {{envelope()?.nota}}</p>}
</section>
}@else{<section class="empty-card"><h3>Un diseño con historia</h3><p>Las pantallas generadas aparecerán aquí con sus versiones, historias de origen y validaciones.</p></section>}
}@else{<p>Selecciona un proyecto para comenzar.</p>}
</div>`})
export class Mockups implements OnDestroy {
 store=inject(Store);sources=signal<any[]>([]);versions=signal<any[]>([]);envelope=signal<any>(null);content=signal<any>(null);selectedVersion=signal(0);screenId=signal('');busy=signal(false);runId=signal('');progress=signal('');showJson=signal(false);simulation=signal('');
 showAnnotations=signal(localStorage.getItem('trama_mockup_annotations')==='true');
 sourceVersion=0;instructions='';target='';reviewNote='';viewport='desktop';private controller?:AbortController;
 constructor(){effect(()=>{const id=this.store.project()?.id_proyecto;this.controller?.abort();this.sources.set([]);this.versions.set([]);this.envelope.set(null);this.content.set(null);this.runId.set('');this.screenId.set('');this.busy.set(false);this.selectedVersion.set(0);this.instructions='';this.target='';this.reviewNote='';this.sourceVersion=0;if(id)void this.load(id);});}
 ngOnDestroy(){this.controller?.abort();}
 base(pid:string){return `/projects/${pid}/mockups`;}
 async load(pid:string){try{const [sources,versions,runs]=await Promise.all([this.store.api.request<any[]>(`/projects/${pid}/backlog`),this.store.api.request<any[]>(this.base(pid)),this.store.api.request<any[]>(`/projects/${pid}/executions`)]);if(pid!==this.store.project()?.id_proyecto)return;this.sources.set(sources.filter(s=>['aprobado_por_humano','validado_automaticamente'].includes(s.estado)));this.versions.set(versions);this.sourceVersion=this.sources()[0]?.version||0;if(versions.length)await this.loadVersion(versions[0].version);const active=runs.find(r=>r.tipo==='mockups'&&['pendiente','ejecutando'].includes(r.estado));if(active)void this.monitor(pid,active.id_ejecucion);}catch(e){this.store.api.showError(e);}}
 async loadVersion(version:number){const pid=this.store.project()?.id_proyecto;if(!pid||!version)return;try{const result=await this.store.api.request<any>(`${this.base(pid)}/${version}`);if(pid!==this.store.project()?.id_proyecto)return;this.envelope.set(result);this.content.set(result.payload);this.selectedVersion.set(version);this.target='';this.reviewNote='';this.showJson.set(false);this.simulation.set('');if(result.payload.diseno.pantallas.length)await this.chooseScreen(result.payload.diseno.pantallas[0].id);}catch(e){this.store.api.showError(e);}}
 toggleAnnotations(){this.showAnnotations.update(value=>!value);localStorage.setItem('trama_mockup_annotations',String(this.showAnnotations()));}
 isExplanatory(control:Control){
   // Compatibilidad con la anotación visual del primer diseño: no ocultar alertas funcionales.
   return control.tipo==='aviso'&&control.clave==='mensaje_estilo_consistente';
 }
 screen():Screen|undefined{return this.content()?.diseno.pantallas.find((s:Screen)=>s.id===this.screenId());}
 criteria(screen:Screen){return [...new Set([...screen.controles.flatMap(c=>c.ids_criterios),...(screen.ids_criterios_visuales||[])])].join(', ')||'Sin vínculos';}
 async chooseScreen(id:string){const pid=this.store.project()?.id_proyecto;const version=this.selectedVersion();this.screenId.set(id);this.simulation.set('');if(pid&&version)try{await this.store.api.request(`${this.base(pid)}/${version}/view`,'POST',{pantalla_id:id});}catch(e){this.store.api.showError(e);}}
 fieldName(row:string){const i=row.indexOf(":");return i>0?row.slice(0,i).trim():row;}
 fieldValue(row:string){const i=row.indexOf(":");return i>0?row.slice(i+1).trim():"";}
 simulate(control:Control){if(control.destino)void this.chooseScreen(control.destino);else this.simulation.set('Acción simulada. No se ha enviado ni guardado información.');}
 async generate(){const pid=this.store.project()?.id_proyecto;if(!pid)return;this.busy.set(true);try{const result=await this.store.api.request<any>(`${this.base(pid)}/generate`,'POST',{version_backlog:this.sourceVersion,id_solicitud:crypto.randomUUID(),instrucciones:this.instructions,pantalla_id:this.target||null,version_base:this.target?this.selectedVersion():null});if(pid!==this.store.project()?.id_proyecto)return;await this.monitor(pid,result.id_ejecucion);}catch(e){this.store.api.showError(e);}finally{if(pid===this.store.project()?.id_proyecto)this.busy.set(false);}}
 async monitor(pid:string,run:string){this.controller?.abort();const controller=new AbortController();this.controller=controller;this.runId.set(run);this.busy.set(true);try{await this.store.api.events(`/projects/${pid}/executions/${run}/events`,(name,data)=>{if(pid!==this.store.project()?.id_proyecto)return;if(name==='actividad')this.progress.set(data.descripcion||data.operacion||'Trabajando…');},controller.signal);if(controller.signal.aborted||pid!==this.store.project()?.id_proyecto)return;const [rows,result]=await Promise.all([this.store.api.request<any[]>(this.base(pid)),this.store.api.request<any>(`/projects/${pid}/executions/${run}`)]);if(pid!==this.store.project()?.id_proyecto)return;this.versions.set(rows);if(result.estado==='error'||result.estado==='interrumpido'){this.progress.set(result.resultado?.tipo_error==='contrato_diseno'?'No se incorporó una propuesta con errores técnicos. No necesitas corregir identificadores; tus versiones anteriores se conservan.':result.resultado?.error||'La ejecución se detuvo. Puedes consultar su estado en Actividad de IA.');return;}this.progress.set('Diseño guardado. Revisa las pantallas y la validación.');if(rows.length)await this.loadVersion(rows[0].version);}catch(e){if(!controller.signal.aborted)this.store.api.showError(e);}finally{if(this.controller===controller)this.busy.set(false);}}
 async review(action:string){const pid=this.store.project()?.id_proyecto;if(!pid)return;this.busy.set(true);try{const result=await this.store.api.request<any>(`${this.base(pid)}/${this.selectedVersion()}/review`,'POST',{accion:action,nota:this.reviewNote});if(pid!==this.store.project()?.id_proyecto)return;this.envelope.set(result);this.versions.set(await this.store.api.request<any[]>(this.base(pid)));}catch(e){this.store.api.showError(e);}finally{if(pid===this.store.project()?.id_proyecto)this.busy.set(false);}}
}
