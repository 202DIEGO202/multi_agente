import { Component, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink,  RouterOutlet } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { Store } from './core/store';
import { Notifications, AppNotification } from './core/notifications';
import { Icon } from './shared/icon';
import { JsonViewer } from './shared/json-viewer';
import { toSignal } from '@angular/core/rxjs-interop';
import { filter, map, startWith } from 'rxjs';

@Component({selector:'app-root', standalone:true, imports:[RouterLink,RouterOutlet,FormsModule,Icon,JsonViewer,DatePipe],
template:`
<div class="app-shell" [class.sidebar-open]="menu()">
  <aside class="sidebar">
    <a routerLink="/" class="brand" (click)="menu.set(false)"><span class="brand-mark">t<span>•</span></span><span>trama<small>FÁBRICA DE SOFTWARE</small></span></a>
    <div class="workspace-label">ESPACIO DE TRABAJO</div>
    <div class="project-selector"><span class="project-symbol">{{store.project()?.nombre?.charAt(0) || '+'}}</span>
      <select aria-label="Proyecto activo" [ngModel]="store.project()?.id_proyecto || ''" (ngModelChange)="store.select($event)">
      @if (!store.projects().length) { <option value="">Crea tu primer proyecto</option> }
      @for (project of store.projects(); track project.id_proyecto) {<option [value]="project.id_proyecto">{{project.nombre}}</option>}
      </select>
    </div>
    <nav aria-label="Navegación principal">@for (item of navigation; track item.path) {
      <a [routerLink]="item.path" [class.active]="groupActive(item.paths)" [attr.aria-current]="groupActive(item.paths)?'page':null" (click)="menu.set(false)"><ui-icon [name]="item.icon"/><span>{{item.label}}</span></a>
    }</nav>
    <div class="workspace-label conversation-label">CONVERSACIONES <button class="icon-button" aria-label="Nueva conversación" [disabled]="!store.project()" (click)="newConversation()"><ui-icon name="plus"/></button></div>
    <div class="sidebar-conversations">@for (chat of store.conversations(); track chat.id) {
      <a routerLink="/chat" (click)="store.openConversation(chat.id); menu.set(false)" [class.selected]="store.conversationId()===chat.id"><span class="conversation-dot"></span>{{chat.titulo}}</a>
    } @empty {<p class="muted tiny">Tus análisis aparecerán aquí.</p>}</div>
    <div class="sidebar-footer"><div class="phase-label"><span class="status-dot"></span> Fases 01–05 <span>Del análisis al producto desplegado</span></div>
      <button class="settings-button" (click)="showSettings()"><span class="avatar small">AF</span><span>Analista funcional<small>Configuración del espacio</small></span><ui-icon name="settings"/></button>
    </div>
  </aside>
  @if(menu()){<button class="sidebar-scrim" aria-label="Cerrar navegación" (click)="menu.set(false)"></button>}
  <div class="workspace"><header class="topbar"><div class="breadcrumb"><button class="icon-button mobile-menu" aria-label="Abrir navegación" (click)="menu.set(!menu())"><ui-icon name="menu"/></button><span>Fábrica de software</span><span class="slash">/</span><strong>{{store.project()?.nombre || 'Tu espacio de trabajo'}}</strong></div>
    <div class="header-actions"><span class="connection" [class.offline]="!connected()"><span class="status-dot"></span>{{connected() ? 'Servidor conectado' : 'Servidor sin conexión'}}</span><div class="notification-anchor"><button class="icon-button notification-bell" [attr.aria-label]="'Notificaciones'+(notifications.unread()?': '+notifications.unread()+' sin leer':'')" [attr.aria-expanded]="panel()" (click)="panel.set(!panel())"><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M18 16v-5a6 6 0 0 0-12 0v5l-2 2h16l-2-2ZM10 20a2 2 0 0 0 4 0" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>@if(notifications.unread()){<span class="notification-badge">{{notifications.unread()}}</span>}</button>
@if(panel()){<section class="notification-panel" role="dialog" aria-label="Notificaciones"><div class="section-heading"><strong>Notificaciones</strong>@if(notifications.unread()){<button class="text-button" (click)="notifications.readAll()">Marcar todas como leídas</button>}</div>
@for(n of notifications.items();track n.id){<button class="notification-item" [class.unread]="!n.leida" (click)="openNotification(n)"><strong>{{n.titulo}}</strong><span>{{n.mensaje}}</span><small class="muted">{{n.proyecto}} · {{n.fecha|date:'dd/MM HH:mm'}}</small></button>}@empty{<p class="muted tiny">No tienes notificaciones.</p>}</section>}</div>
<button class="icon-button" (click)="toggleTheme()" aria-label="Cambiar tema"><ui-icon name="sun"/></button><span class="avatar small">AF</span></div>
  </header>
  @if(store.api.error()){<div class="error-banner" role="alert"><span>{{store.api.error()}}</span><button class="icon-button" aria-label="Cerrar error" (click)="store.api.error.set('')"><ui-icon name="close"/></button></div>}
  <main><router-outlet/></main>@if(notifications.toast();as t){<div class="notification-toast" role="status" aria-live="polite"><div><strong>{{t.titulo}}</strong><span>{{t.mensaje}}</span></div><div class="mockup-actions"><button class="button primary" (click)="openNotification(t)">Ver</button><button class="icon-button" aria-label="Cerrar aviso" (click)="notifications.toast.set(null)"><ui-icon name="close"/></button></div></div>}<footer class="app-footer"><span>TRAMA · ANÁLISIS Y DISEÑO</span><span>Del conocimiento a las historias.</span></footer></div>
</div>
@if(settingsOpen()){<div class="modal-backdrop" (click)="settingsOpen.set(false)"><section class="modal" role="dialog" aria-modal="true" aria-label="Configuración" (click)="$event.stopPropagation()"><div class="section-heading"><h2>Configuración del espacio</h2><button class="icon-button" aria-label="Cerrar configuración" (click)="settingsOpen.set(false)"><ui-icon name="close"/></button></div>
<p class="muted">Los modelos se configuran en el servidor. Las credenciales de IA permanecen allí.</p><label>Clave de acceso al servidor (si está habilitada)<input type="password" [(ngModel)]="accessToken" autocomplete="off" placeholder="Clave de acceso"/></label><button class="button primary" (click)="saveAccess()">Guardar acceso</button>@if(configuration()){<json-viewer [value]="configuration()"/>}</section></div>}
`})
export class App {
  store=inject(Store); notifications=inject(Notifications); panel=signal(false); menu=signal(false); settingsOpen=signal(false); connected=signal(false);
  configuration=signal<unknown>(null); accessToken='';
  private router=inject(Router);
  private currentUrl=toSignal(this.router.events.pipe(filter((event):event is NavigationEnd=>event instanceof NavigationEnd),map(event=>event.urlAfterRedirects),startWith(this.router.url)),{initialValue:this.router.url});
  navigation=[
    {path:'/',label:'Vista general',icon:'grid',paths:['/']},
    {path:'/workflow',label:'Flujo de desarrollo',icon:'flow',paths:['/workflow','/chat','/state','/backlog','/mockups','/architecture','/construction']},
    {path:'/knowledge',label:'Conocimiento y actividad',icon:'book',paths:['/knowledge','/rag','/activity']}
  ];
  groupActive(paths:string[]){return paths.includes(this.currentUrl().split('?')[0]);}
  constructor(){
    document.documentElement.dataset['theme']=localStorage.getItem('fabrica_theme')||'light';
    void this.store.init(); void this.checkConnection(); this.notifications.start();
  }
  async openNotification(n:AppNotification){this.panel.set(false);this.notifications.toast.set(null);try{await this.notifications.read(n);if(this.store.project()?.id_proyecto!==n.id_proyecto)await this.store.select(n.id_proyecto);if(n.enlace)await this.router.navigateByUrl(n.enlace);}catch(error){this.store.api.showError(error);}}
  async checkConnection(){try{await this.store.api.request('/health');this.connected.set(true);}catch{this.connected.set(false);}}
  toggleTheme(){const theme=document.documentElement.dataset['theme']==='dark'?'light':'dark';document.documentElement.dataset['theme']=theme;localStorage.setItem('fabrica_theme',theme);}
  async newConversation(){try{await this.store.newConversation();}catch(error){this.store.api.showError(error);}}
  async showSettings(){this.settingsOpen.set(true);this.accessToken=sessionStorage.getItem('fabrica_access')||'';try{this.configuration.set(await this.store.api.request('/configuration'));}catch(error){this.store.api.showError(error);}}
  async saveAccess(){sessionStorage.setItem('fabrica_access',this.accessToken);await this.checkConnection();await this.store.init();await this.showSettings();}
}
