/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 'http'면 실제 서버(`pnpm dev:http`), 그 밖에는 mock(기본). `src/gateway/mode.ts`가 읽는다. */
  readonly VITE_GATEWAY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
