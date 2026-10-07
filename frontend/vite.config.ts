/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// 개발 서버는 /api를 백엔드로 넘겨 브라우저가 같은 출처로 보게 한다(쿠키 인증·CORS 회피).
// 운영에서는 Nginx가 같은 구성을 맡는다.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
