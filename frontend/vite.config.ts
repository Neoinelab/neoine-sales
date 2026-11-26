/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// 개발 서버는 /api를 백엔드로 넘겨 브라우저가 같은 출처로 보게 한다(쿠키 인증·CORS 회피).
// OS 직접 실행 환경에서는 Nginx가 모든 웹 요청을 이 Vite 서버로 넘기고, Vite가 /api만 FastAPI로 넘긴다.
// docker compose product 환경은 web 컨테이너의 Nginx가 dist와 /api를 직접 처리하는 별도 배포 방식이다.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000' },
    // 외부 접속을 허용하려면 host 설정도 함께 필요
    host: true,
    allowedHosts: [
      'salesx.neoine.co.kr', // 특정 도메인 허용
    ],
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
