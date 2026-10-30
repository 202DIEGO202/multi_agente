import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RevisionScreen, revisionTemplate } from './revision';

@Component({ selector: 'app-talento-humano', standalone: true, imports: [CommonModule, FormsModule], template: revisionTemplate })
export class TalentoHumanoComponent extends RevisionScreen {
  readonly rol = 'TALENTO_HUMANO';
  readonly titulo = 'Validación de Talento Humano';
  readonly etiquetaObservacion = 'Observaciones de Talento Humano';
}