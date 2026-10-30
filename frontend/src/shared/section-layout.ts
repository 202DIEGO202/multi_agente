import { Component, inject } from '@angular/core';
import { ActivatedRoute, NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { filter, map, startWith } from 'rxjs';

@Component({standalone:true,imports:[RouterLink,RouterLinkActive,RouterOutlet],template:`
<section class="section-navigation" [attr.aria-label]="workflow?'Flujo de desarrollo':'Conocimiento y actividad'">
<div class="section-navigation-heading"><div><div class="eyebrow">{{workflow?'FLUJO DE DESARROLLO':'CONOCIMIENTO Y ACTIVIDAD'}}</div><h2>{{workflow?'Una idea, paso a paso.':'Documentos, búsquedas y registros.'}}</h2></div><span class="section-navigation-note">{{workflow?'Cada etapa parte de la anterior':'Todo el contexto de tu proyecto'}}</span></div>
<nav [attr.aria-label]="workflow?'Etapas del desarrollo':'Secciones de conocimiento y actividad'" [class.workflow-navigation]="workflow" [class.resource-navigation]="!workflow">
@for(item of items;track item.path){<a [routerLink]="item.path" [queryParamsHandling]="workflow?'':'preserve'" routerLinkActive="selected" [routerLinkActiveOptions]="{exact:true}" [attr.aria-current]="currentPath()===item.path?'page':null">
@if(workflow){<span class="stage-number">{{item.number}}</span>}<span class="section-tab-copy"><strong>{{item.label}}</strong><small>{{item.subtitle}}</small></span>@if(workflow&&item.number<6){<span class="stage-arrow" aria-hidden="true">→</span>}</a>}
</nav>
@if(workflow){<p class="stage-dependency"><span class="stage-dependency-label">{{active()?.label}}</span> {{active()?.detail}}</p>}
</section>
<router-outlet/>
`})
export class SectionLayout {
 private route=inject(ActivatedRoute); private router=inject(Router);
 workflow=this.route.snapshot.data['section']==='workflow';
 private currentUrl=toSignal(this.router.events.pipe(filter((event):event is NavigationEnd=>event instanceof NavigationEnd),map(event=>event.urlAfterRedirects),startWith(this.router.url)),{initialValue:this.router.url});
 private stages=[
  {path:'/chat',number:1,label:'Chat del analista',subtitle:'Definir necesidades',detail:'Aquí comienza el proceso. Las propuestas se revisan en Estado del proyecto.'},
  {path:'/state',number:2,label:'Estado del proyecto',subtitle:'Revisar y publicar requisitos',detail:'Parte de las propuestas del chat. Aprueba los requisitos y publica una línea base para continuar.'},
  {path:'/backlog',number:3,label:'Generación de backlog',subtitle:'Épicas, features e historias',detail:'Depende de una línea base publicada en Estado del proyecto. Revisa y publica el backlog para pasar al diseño.'},
  {path:'/mockups',number:4,label:'Diseño funcional',subtitle:'Pantallas y mockups',detail:'Depende de un backlog aprobado y publicado. Aquí generas, revisas y publicas sus pantallas.'},
  {path:'/architecture',number:5,label:'Arquitectura',subtitle:'Calidad, C4 e infraestructura',detail:'Depende de un backlog publicado (y usa los mockups aprobados). Genera arquitectura, diagramas, archivos de despliegue y plan técnico.'},
  {path:'/construction',number:6,label:'Construcción',subtitle:'Código, pruebas, IaC y entorno',detail:'Depende de una arquitectura aprobada. Los agentes construyen el producto, lo validan y lo montan en local; recibirás una notificación al terminar.'}
 ];
 private resources=[
  {path:'/knowledge',number:0,label:'Conocimiento',subtitle:'Documentos y fuentes',detail:''},
  {path:'/rag',number:0,label:'Trazabilidad RAG',subtitle:'Búsqueda y evidencia',detail:''},
  {path:'/activity',number:0,label:'Actividad de IA',subtitle:'Ejecuciones y registros',detail:''}
 ];
 items=this.workflow?this.stages:this.resources;
 currentPath(){return this.currentUrl().split('?')[0];}
 active(){return this.items.find(item=>item.path===this.currentPath());}
}
