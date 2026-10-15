import { Navigate } from 'react-router'
import { useMe } from '../../data/auth'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { Layout } from '../../shared/ui/Layout'

/** 로그인하지 않았으면 로그인 화면으로 보낸다. 로그인했으면 공통 레이아웃 안에 하위 화면을 보여준다. */
export function RequireAuth() {
  const me = useMe()
  if (me.isPending) return <p className="content">불러오는 중…</p>
  if (me.error?.status === 401) return <Navigate to="/login" replace />
  if (me.isError) return <ErrorBanner error={me.error} />
  return <Layout />
}
