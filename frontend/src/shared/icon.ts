import { Component, input } from '@angular/core';
const paths: Record<string,string> = {
  grid:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  chat:'M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5z',
  layers:'m12 3 10 6-10 6L2 9z M2 15l10 6 10-6 M2 12l10 6 10-6',
  book:'M4 3h7a3 3 0 0 1 3 3v15a4 4 0 0 0-4-3H4z M14 6a3 3 0 0 1 3-3h5v15h-5a3 3 0 0 0-3 3',
  flow:'M4 3h6v5H4z M15 16h6v5h-6z M4 16h6v5H4z M7 8v5h11v3 M7 13v3',
  pulse:'M2 12h4l3-8 6 16 3-8h4', plus:'M12 5v14 M5 12h14',
  arrow:'M5 12h14 M12 5l7 7-7 7', send:'m22 2-7 20-4-9L2 9z M22 2 11 13',
  file:'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 13h8 M8 17h5',
  trash:'M3 6h18 M9 6V3h6v3 M5 6l1 15h12l1-15 M10 10v7 M14 10v7',
  check:'m5 12 4 4L19 6', close:'M6 6l12 12 M18 6 6 18',
  sun:'M12 2v2 M12 20v2 M2 12h2 M20 12h2 M5 5l1 1 M18 18l1 1 M5 19l1-1 M18 6l1-1 M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  upload:'M12 16V3 M7 8l5-5 5 5 M3 16v5h18v-5',
  search:'M21 21l-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  menu:'M3 6h18 M3 12h18 M3 18h18', settings:'M4 7h16 M4 17h16 M8 4v6 M16 14v6',
};
@Component({selector:'ui-icon', standalone:true, template:`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path [attr.d]="path()"/></svg>`, styles:[`:host{display:inline-flex;width:20px;height:20px;flex-shrink:0}svg{width:100%;height:100%}`]})
export class Icon { name = input('grid'); path() { return paths[this.name()] || paths['file']; } }
