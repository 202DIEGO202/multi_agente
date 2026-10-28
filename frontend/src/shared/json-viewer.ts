import { Component, computed, input, signal } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({selector:'json-viewer', standalone:true, imports:[CommonModule], template:`
<div class="json-toolbar"><span>JSON · esquema {{schemaVersion()}}</span><button class="text-button" (click)="copy()">{{copied() ? 'Copiado' : 'Copiar JSON'}}</button></div>
<pre class="json-code" tabindex="0" aria-label="Contrato JSON">@for (token of tokens(); track $index) {<span [class]="token.kind">{{token.text}}</span>}</pre>`})
export class JsonViewer {
  value = input<unknown>(); copied = signal(false);
  schemaVersion=computed(()=>{const value=this.value();return value&&typeof value==='object'&&'version_esquema' in value?String(value.version_esquema):'—';});
  formatted = computed(() => JSON.stringify(this.value(), null, 2) || '{}');
  tokens = computed(() => {
    const regex = /("(?:\\.|[^"\\])*"\s*:|"(?:\\.|[^"\\])*"|\b(?:true|false|null)\b|\b-?\d+(?:\.\d+)?\b)/g;
    const text = this.formatted(); let start=0, match; const tokens:{text:string;kind:string}[]=[];
    while ((match=regex.exec(text))) {
      tokens.push({text:text.slice(start,match.index),kind:''});
      tokens.push({text:match[0],kind:match[0].endsWith(':')?'json-key':match[0].startsWith('"')?'json-string':'json-number'});
      start=regex.lastIndex;
    }
    tokens.push({text:text.slice(start),kind:''}); return tokens;
  });
  async copy() { try { await navigator.clipboard.writeText(this.formatted()); this.copied.set(true); setTimeout(()=>this.copied.set(false),2000); } catch { this.copied.set(false); } }
}
