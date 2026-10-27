/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  /** Painel publicado na web: projeto Supabase gravado no build. */
  readonly VITE_PAINEL_SUPABASE_URL?: string;
  readonly VITE_PAINEL_SUPABASE_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
