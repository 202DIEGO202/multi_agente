import { Injectable, computed, inject, signal } from '@angular/core';
import { ApiService } from './api.service';

export interface AppNotification {id:number;id_proyecto:string;proyecto:string;tipo:string;titulo:string;mensaje:string;enlace:string|null;leida:string|null;fecha:string;}

/** Avisos de tareas largas (construcción, entorno local): llegan aunque el usuario esté en otra página. */
@Injectable({providedIn:'root'})
export class Notifications {
  private api=inject(ApiService);
  items=signal<AppNotification[]>([]);
  toast=signal<AppNotification|null>(null);
  unread=computed(()=>this.items().filter(n=>!n.leida).length);
  private lastId=-1;private timer?:ReturnType<typeof setInterval>;private toastTimer?:ReturnType<typeof setTimeout>;
  start(){if(this.timer)return;void this.refresh();this.timer=setInterval(()=>void this.refresh(),10000);}
  async refresh(){
    try{
      const rows=await this.api.request<AppNotification[]>('/notifications');
      const newest=rows[0]?.id??0;
      // En la primera carga no se muestran avisos antiguos; solo los que lleguen después.
      if(this.lastId>=0){const fresh=rows.find(n=>n.id>this.lastId&&!n.leida);if(fresh)this.show(fresh);}
      this.lastId=Math.max(this.lastId,newest);this.items.set(rows);
    }catch{/* El indicador de conexión ya informa la falta de servidor. */}
  }
  show(n:AppNotification){this.toast.set(n);clearTimeout(this.toastTimer);this.toastTimer=setTimeout(()=>this.toast.set(null),9000);}
  async read(n:AppNotification){if(n.leida)return;await this.api.request(`/notifications/${n.id}/read`,'POST');this.items.update(r=>r.map(x=>x.id===n.id?{...x,leida:new Date().toISOString()}:x));}
  async readAll(){await this.api.request('/notifications/read-all','POST');this.items.update(r=>r.map(x=>({...x,leida:x.leida||new Date().toISOString()})));}
}
