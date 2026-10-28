import { Component, computed, input } from '@angular/core';

/** Dibuja las vistas que calcula el backend (posiciones incluidas). Sin librerías ni HTML generado por IA. */
export interface DiagramNode {id:string;etiqueta:string;detalle:string;grupo:string;x:number;y:number;w:number;h:number;}
export interface DiagramEdge {origen:string;destino:string;etiqueta:string;}
export interface DiagramStep {de:string;a:string;mensaje:string;alternativa:boolean;}
export interface DiagramView {id:string;tipo:'grafo'|'secuencia';titulo:string;explicacion:string;ancho?:number;alto?:number;nodos?:DiagramNode[];aristas?:DiagramEdge[];participantes?:{id:string;etiqueta:string}[];pasos?:DiagramStep[];condicion_alternativa?:string|null;mermaid:string;}

const LANE=210, HEAD=64, TOP=HEAD+44, ROW=62;
const KIND:Record<string,string>={sistema:'Sistema',externo:'Externo',servicio_externo:'Externo',aplicacion_web:'Web',api:'API',base_datos:'Base de datos',modulo_ui:'UI',controlador:'Controlador',servicio:'Servicio',repositorio:'Repositorio',integracion:'Integración',esquema_datos:'Datos',contenedor:'Contenedor',balanceador:'Balanceador',secreto:'Secreto',registro_imagenes:'Registro',monitoreo:'Monitoreo',paso:'Paso',alternativa:'Alternativa'};
const CYLINDER=new Set(['base_datos','esquema_datos']);

/** Parte un texto en líneas por palabras; la última línea termina en … si sobra texto. */
export function wrap(text:string,size:number,lines:number):string[]{
  const words=(text||'').split(/\s+/).filter(Boolean),out:string[]=[];let line='',used=0;
  for(const word of words){
    const next=line?line+' '+word:word;
    if(next.length<=size){line=next;used++;continue;}
    if(line)out.push(line);
    if(out.length===lines){line='';break;}
    line=word.length>size?word.slice(0,size-1)+'…':word;used++;
  }
  if(line&&out.length<lines)out.push(line);
  if(used<words.length&&out.length){const last=out[out.length-1];out[out.length-1]=(last.length>=size?last.slice(0,size-1):last)+'…';}
  return out;
}

@Component({selector:'ui-diagram',standalone:true,template:`
@if(view();as v){
@if(v.tipo==='grafo'){
<svg class="diagram" [attr.width]="v.ancho" [attr.height]="v.alto" [attr.viewBox]="'0 0 '+v.ancho+' '+v.alto" role="img" [attr.aria-label]="v.titulo">
<defs><marker [attr.id]="'arrow-'+v.id" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="diagram-arrow"/></marker></defs>
@for(e of edges();track $index){<path [attr.d]="e.path" class="diagram-edge" [attr.marker-end]="'url(#arrow-'+v.id+')'">@if(e.full){<title>{{e.full}}</title>}</path>}
@for(n of v.nodos;track n.id){<g [attr.class]="'diagram-node group-'+n.grupo"><title>{{n.etiqueta}} · {{n.detalle}}</title>
@if(n.grupo==='decision'){<polygon [attr.points]="diamond(n)"/>}
@else if(isCylinder(n)){<path [attr.d]="cylinder(n)"/><path [attr.d]="cylinderTop(n)" class="diagram-cylinder-top"/>}
@else{<rect [attr.x]="n.x" [attr.y]="n.y" [attr.width]="n.w" [attr.height]="n.h" [attr.rx]="n.grupo==='persona'?n.h/2:12"/>}
@if(kind(n.grupo)){<text [attr.x]="n.x+12" [attr.y]="n.y+(isCylinder(n)?32:17)" class="diagram-kind">{{kind(n.grupo)}}</text>}
@for(line of titleLines(n);track $index){<text [attr.x]="n.x+n.w/2" [attr.y]="titleY(n)+$index*17" text-anchor="middle" class="diagram-title">{{line}}</text>}
@for(line of detailLines(n);track $index){<text [attr.x]="n.x+n.w/2" [attr.y]="titleY(n)+titleLines(n).length*17+1+$index*14" text-anchor="middle" class="diagram-detail">{{line}}</text>}
</g>}
@for(e of edges();track $index){@if(e.lines.length){<g class="diagram-label"><title>{{e.full}}</title><rect [attr.x]="e.lx-e.lw/2" [attr.y]="e.ly-e.lh/2" [attr.width]="e.lw" [attr.height]="e.lh" rx="10"/>@for(line of e.lines;track $index){<text [attr.x]="e.lx" [attr.y]="e.ly+4-(e.lines.length-1)*7+$index*14" text-anchor="middle">{{line}}</text>}</g>}}
</svg>}
@else{
<svg class="diagram" [attr.width]="seqWidth()" [attr.height]="seqHeight()" [attr.viewBox]="'0 0 '+seqWidth()+' '+seqHeight()" role="img" [attr.aria-label]="v.titulo">
<defs><marker [attr.id]="'arrow-'+v.id" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="diagram-arrow"/></marker></defs>
@for(p of v.participantes;track p.id;let i=$index){<line [attr.x1]="i*LANE+LANE/2" [attr.y1]="HEAD+10" [attr.x2]="i*LANE+LANE/2" [attr.y2]="seqHeight()-12" class="diagram-lifeline"/>}
@if(altStart()>=0){<rect x="6" [attr.y]="TOP+altStart()*ROW-42" [attr.width]="seqWidth()-12" [attr.height]="(v.pasos!.length-altStart())*ROW+14" rx="10" class="diagram-alt"/><g class="diagram-label diagram-label-alt"><rect x="14" [attr.y]="TOP+altStart()*ROW-53" [attr.width]="altLabel().length*6.6+28" height="22" rx="11"/><text x="28" [attr.y]="TOP+altStart()*ROW-38">{{altLabel()}}</text></g>}
@for(s of v.pasos;track $index;let i=$index){
<line [attr.x1]="lane(s.de)" [attr.y1]="TOP+i*ROW" [attr.x2]="lane(s.a)+(lane(s.a)>lane(s.de)?-4:4)" [attr.y2]="TOP+i*ROW" class="diagram-edge" [class.diagram-edge-alt]="s.alternativa" [attr.marker-end]="'url(#arrow-'+v.id+')'"/>
@for(line of stepLines(s);track $index;let j=$index){<text [attr.x]="(lane(s.de)+lane(s.a))/2" [attr.y]="TOP+i*ROW-8-(stepLines(s).length-1-j)*15" text-anchor="middle" class="diagram-message">@if(j===0){<tspan class="diagram-step">{{i+1}}. </tspan>}{{line}}</text>}}
@for(p of v.participantes;track p.id;let i=$index){<g class="diagram-node group-participante"><title>{{p.etiqueta}}</title><rect [attr.x]="i*LANE+12" y="8" [attr.width]="LANE-24" [attr.height]="HEAD-8" rx="12"/>@for(line of headLines(p.etiqueta);track $index){<text [attr.x]="i*LANE+LANE/2" [attr.y]="HEAD/2+9-(headLines(p.etiqueta).length-1)*8+$index*16" text-anchor="middle" class="diagram-title">{{line}}</text>}</g>}
</svg>}
}`})
export class Diagram {
  view=input.required<DiagramView>();
  LANE=LANE;HEAD=HEAD;TOP=TOP;ROW=ROW;
  edges=computed(()=>{
    const v=this.view();const nodes=new Map((v.nodos||[]).map(n=>[n.id,n]));
    const result=(v.aristas||[]).flatMap(e=>{const a=nodes.get(e.origen),b=nodes.get(e.destino);if(!a||!b)return [];
      const [x1,y1,x2,y2,vertical]=this.anchors(a,b);const mx=(x1+x2)/2,my=(y1+y2)/2;
      // Si otro nodo queda en medio, la flecha lo rodea por el lado con más espacio.
      const blockers=(v.nodos||[]).filter(n=>n!==a&&n!==b&&n.y<Math.max(y1,y2)&&n.y+n.h>Math.min(y1,y2)&&n.x<Math.max(x1,x2)+12&&n.x+n.w>Math.min(x1,x2)-12);
      let path:string,spots:[number,number][];
      if(vertical&&blockers.length){
        const left=Math.min(...blockers.map(n=>n.x)),right=Math.max(...blockers.map(n=>n.x+n.w));
        const side=(v.ancho||0)-right>=left?right+28:left-28;
        path=`M${x1},${y1} C${x1},${y1+40} ${side},${y1+20} ${side},${my} S${x2},${y2-40} ${x2},${y2}`;
        spots=[[side,my],[side,my-24],[side,my+24]];
      }else{
        const c=vertical?[[x1,my],[x2,my]]:[[mx,y1],[mx,y2]];
        path=`M${x1},${y1} C${c[0][0]},${c[0][1]} ${c[1][0]},${c[1][1]} ${x2},${y2}`;
        // Puntos sobre la propia curva: la etiqueta se mueve por su flecha, nunca se separa de ella.
        spots=[0.5,0.62,0.38,0.74,0.26,0.84,0.16].map(t=>this.bezier(t,[x1,y1],c[0] as [number,number],c[1] as [number,number],[x2,y2]));
      }
      const lines=e.etiqueta?wrap(e.etiqueta,30,2):[];
      const lw=Math.max(0,...lines.map(l=>l.length))*6.3+20,lh=lines.length>1?34:20;
      return [{path,lines,full:e.etiqueta,spots,dir:x2-x1,lx:spots[0][0],ly:spots[0][1],lw,lh}];});
    // Las etiquetas nunca tapan un nodo ni otra etiqueta; si no caben, quedan como tooltip de la flecha.
    const placed:{x:number;y:number;w:number;h:number}[]=[];
    const hits=(x:number,y:number,w:number,h:number)=>(v.nodos||[]).some(n=>x+w/2>n.x-4&&x-w/2<n.x+n.w+4&&y+h/2>n.y-2&&y-h/2<n.y+n.h+2)
      ||placed.some(p=>Math.abs(p.x-x)<(p.w+w)/2+4&&Math.abs(p.y-y)<(p.h+h)/2+4);
    for(const e of result){if(!e.lines.length)continue;
      // Primero sobre la línea; si choca, pegada al costado de su línea, hacia donde se abre la flecha.
      const side=e.dir>=0?1:-1;
      const options=[...e.spots,...e.spots.map(([x,y])=>[x+side*(e.lw/2+8),y] as [number,number])];
      const spot=options.find(([x,y])=>!hits(x,y,e.lw,e.lh));
      if(!spot)e.lines=[];else{[e.lx,e.ly]=spot;placed.push({x:e.lx,y:e.ly,w:e.lw,h:e.lh});}}
    return result;
  });
  bezier(t:number,p0:[number,number],p1:[number,number],p2:[number,number],p3:[number,number]):[number,number]{
    const u=1-t,k=[u*u*u,3*u*u*t,3*u*t*t,t*t*t];
    return [k[0]*p0[0]+k[1]*p1[0]+k[2]*p2[0]+k[3]*p3[0],k[0]*p0[1]+k[1]*p1[1]+k[2]*p2[1]+k[3]*p3[1]];
  }
  seqWidth=computed(()=>Math.max(1,(this.view().participantes||[]).length)*LANE);
  seqHeight=computed(()=>TOP+(this.view().pasos||[]).length*ROW);
  altStart=computed(()=>(this.view().pasos||[]).findIndex(s=>s.alternativa));
  altLabel=computed(()=>'Alternativa · '+(wrap(this.view().condicion_alternativa||'Camino alternativo',60,1)[0]||''));
  lane(id:string){return (this.view().participantes||[]).findIndex(p=>p.id===id)*LANE+LANE/2;}
  kind(group:string){return KIND[group]||'';}
  isCylinder(n:DiagramNode){return CYLINDER.has(n.grupo);}
  titleLines(n:DiagramNode){return wrap(n.etiqueta,Math.floor(n.w/8.4),n.grupo==='decision'?3:2);}
  detailLines(n:DiagramNode){return n.grupo==='decision'?[]:wrap(n.detalle,Math.floor(n.w/6.6),n.grupo==='persona'?1:2);}
  titleY(n:DiagramNode){const lines=this.titleLines(n).length+this.detailLines(n).length;const offset=this.isCylinder(n)?10:this.kind(n.grupo)?6:0;return n.y+n.h/2-(lines-1)*8+5+offset;}
  headLines(text:string){return wrap(text,Math.floor((LANE-36)/7.6),2);}
  stepLines(s:DiagramStep){const span=Math.abs(this.lane(s.a)-this.lane(s.de));return wrap(s.mensaje,Math.max(24,Math.floor((span||LANE)/6.9)),2);}
  diamond(n:DiagramNode){return `${n.x+n.w/2},${n.y} ${n.x+n.w},${n.y+n.h/2} ${n.x+n.w/2},${n.y+n.h} ${n.x},${n.y+n.h/2}`;}
  cylinder(n:DiagramNode){const r=10;return `M${n.x},${n.y+r} A${n.w/2},${r} 0 0 1 ${n.x+n.w},${n.y+r} V${n.y+n.h-r} A${n.w/2},${r} 0 0 1 ${n.x},${n.y+n.h-r} Z`;}
  cylinderTop(n:DiagramNode){const r=10;return `M${n.x},${n.y+r} A${n.w/2},${r} 0 0 0 ${n.x+n.w},${n.y+r}`;}
  /** Une borde inferior con superior entre filas, o los laterales si están en la misma fila. */
  anchors(a:DiagramNode,b:DiagramNode):[number,number,number,number,boolean]{
    const acx=a.x+a.w/2,bcx=b.x+b.w/2;
    if(b.y>=a.y+a.h)return [acx,a.y+a.h,bcx,b.y-2,true];
    if(a.y>=b.y+b.h)return [acx,a.y,bcx,b.y+b.h+2,true];
    const right=bcx>acx;return [right?a.x+a.w:a.x,a.y+a.h/2,right?b.x-2:b.x+b.w+2,b.y+b.h/2,false];
  }
}
