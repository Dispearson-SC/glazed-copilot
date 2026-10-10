import { useEffect, useState } from "react";
import { useApi } from "../ApiContext";
import type { VoiceConfig } from "../types";

export interface VoiceConfigState {
  /** The config request settled (answered or failed). */
  loaded: boolean;
  /** null while loading or when the request failed: the browser fallbacks apply. */
  config: VoiceConfig | null;
}

/** Fetches GET /voice/config once. A failure is not an error: voice falls back to the browser. */
export function useVoiceConfig(): VoiceConfigState {
  const api = useApi();
  const [state, setState] = useState<VoiceConfigState>({ loaded: false, config: null });
  useEffect(() => {
    let alive = true;
    void Promise.resolve()
      .then(() => api.getVoiceConfig())
      .then((c) => alive && setState({ loaded: true, config: c }))
      .catch(() => alive && setState({ loaded: true, config: null }));
    return () => {
      alive = false;
    };
  }, [api]);
  return state;
}
