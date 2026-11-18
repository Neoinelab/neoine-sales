import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider, useRouteError } from 'react-router'
import { App } from './App'
import './index.css'

/** RouterProvider 기본 오류 화면이 렌더 오류를 삼키지 않도록 다시 던진다(BrowserRouter 때와 같은 동작). */
function RethrowRouteError(): never {
  throw useRouteError()
}

// useBlocker(작성 중 뒤로 가기 확인)는 데이터 라우터에서만 동작한다. 라우트 정의는 App.tsx 한 곳.
const router = createBrowserRouter([{ path: '*', element: <App />, ErrorBoundary: RethrowRouteError }])

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
