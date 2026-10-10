/**
 * Copilot view models. Types only plus pure adapters from the public API shapes:
 * the app ships no sample data, every value comes from the backend or is shown as "Sin datos".
 */

export type Tab = "agente" | "decisiones" | "sucursal" | "memorias" | "alertas";
export type DayKey = "ayer" | "hoy" | "manana";
export type MemoryCategory = "proveedores" | "demanda" | "eventos" | "preferencias";

export interface Memory {
  id: string;
  cat: MemoryCategory;
  /** Material Symbols icon name. */
  icon: string;
  tag: string;
  text: string;
  src: string;
  conf: string;
  isNew?: boolean;
}

/** An analysis or dialogue card shown in the chat, anchored after `at` chat messages. */
export interface AnalysisRef {
  id: string;
  itemId: string;
  mode: "analizar" | "dialogo";
  at: number;
}

/** The decision or warning the chat is currently about ("Hablando de: …"). */
export interface CopilotContext {
  id: string;
  title: string;
}
