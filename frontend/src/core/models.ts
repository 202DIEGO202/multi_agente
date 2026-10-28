export interface Project { id_proyecto: string; nombre: string; descripcion: string; modo: string; version_estado: number; elementos?: number; documentos?: number; fecha_creacion: string; fecha_eliminacion?: string; }
export interface Conversation { id: string; titulo: string; fecha?: string; }
export interface Item { id: string; tipo: string; descripcion: string; version: number; estado: string; vigencia: string; referencias: string[]; fuentes_documentales?: string[]; fecha_modificacion: string; id_mensaje: string; id_ejecucion: string; }
export interface Change { operacion: string; tipo: string; descripcion: string; id_elemento?: string; version_esperada?: number; referencias: string[]; fuentes_documentales?: string[]; }
export interface Proposal { id: string; cambio: Change; estado: string; validacion: string[]; id_elemento?: string; }
export interface Conflict { id: string; descripcion: string; resolucion?: string; fecha_resolucion?: string; }
export interface ProjectState { conocimiento?: {documentos_indexados:number; fragmentos:number}; proyecto: Project; elementos: Item[]; propuestas: Proposal[]; contradicciones: Conflict[]; lineas_base: {version: number; fecha: string}[]; }
export interface Source { id_documento: string; id_fragmento: string; documento: string; contenido: string; pagina: number; version_documento: number; [key: string]: unknown; }
export interface Message { id: string; rol: string; contenido: string; fuentes: Source[]; id_ejecucion: string; }
export interface Activity { id_evento: number; id_ejecucion: string; fecha: string; componente: string; operacion: string; estado: string; descripcion: string; datos: Record<string, any>; duracion_ms?: number; }
export interface Execution { id_ejecucion: string; tipo: string; estado: string; id_conversacion?: string; fecha: string; }
export interface DocumentRecord { id: string; nombre: string; tipo: string; categoria: string; estado: string; version: number; fragmentos: number; ultimo_error?: string; compartido?: boolean; proyecto_origen?: string; }
export interface RunResult { id_ejecucion: string; tipo: string; estado: string; resultado: any; eventos: Activity[]; }
