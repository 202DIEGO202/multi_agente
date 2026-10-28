export interface SourceRef { id: string; version: number; }
export interface Criterion { id: string; dado: string; cuando: string; entonces: string; }
export interface BacklogItem {
  id: string; version: number; titulo: string; descripcion: string;
  requisitos_origen: SourceRef[]; id_epica?: string; id_feature?: string;
  actor?: SourceRef; como?: string; quiero?: string; para?: string;
  criterios_aceptacion?: Criterion[];
}
export interface Finding { severidad: 'error'|'advertencia'; codigo: string; descripcion: string; ids_elementos: string[]; }
export interface BacklogContent {
  version_esquema: string; id_proyecto: string; version_backlog: number;
  version_linea_base_origen: number; version_estado_origen: number; id_ejecucion: string;
  fecha: string; operacion: string; nota: string;
  epicas: BacklogItem[]; features: BacklogItem[]; historias: BacklogItem[];
  preguntas_pendientes: string[];
  validacion: {estructural: boolean; semantica: string; observaciones: Finding[];
    requisitos_sin_cobertura: string[]; puede_publicar: boolean;};
}
export interface BacklogVersion {version:number; version_linea_base:number; fecha:string; estado:string; operacion:string; id_ejecucion:string;}
export interface BacklogEnvelope {
  contrato: BacklogContent; estado: string; publicado: boolean; desactualizado: boolean;
  origenes_modificados: string[]; elementos_afectados: string[];
  decision?: {estado:string; nota:string; fecha:string};
  cambios: {creados:string[]; modificados:string[]; retirados:string[]};
}
