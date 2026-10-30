import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RevisionScreen, revisionTemplate } from './revision';

@Component({ selector: 'app-jefe', standalone: true, imports: [CommonModule, FormsModule], template: revisionTemplate })
export class JefeComponent extends RevisionScreen {
  readonly rol = 'JEFE_INMEDIATO';
  readonly titulo = 'Bandeja de revisión - Jefe inmediato';
  readonly etiquetaObservacion = 'Observaciones de revisión del jefe';
}