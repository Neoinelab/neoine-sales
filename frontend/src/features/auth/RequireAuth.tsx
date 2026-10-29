import { Navigate } from 'react-router'
import { useMe } from '../../data/auth'
import { useServerTimeSync } from '../../data/time'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { Layout } from '../../shared/ui/Layout'
import { DirectoryWarningDialog } from './DirectoryWarningDialog'

/**
 * 로그인하지 않았으면 로그인 화면으로 보낸다. 로그인했으면 서버 시각으로 시계를 맞춘 뒤 공통 레이아웃 안에 하위 화면을 보여준다.
 * 첫 동기 전에는 화면을 보류한다(브라우저 시계로 잠깐 그리지 않는다). 재동기 오류는 화면을 막지 않는다.
 */
export function RequireAuth() {
  const me = useMe()
  const time = useServerTimeSync(me.isSuccess)
  if (me.isPending) return <p className="content">불러오는 중…</p>
  if (me.error?.status === 401) return <Navigate to="/login" replace />
  if (me.isError) return <ErrorBanner error={me.error} />
  if (time.isPending) return <p className="content">불러오는 중…</p>
  if (!time.data && time.isError) return <ErrorBanner error={time.error} />
  return (
    <>
      <Layout />
      <DirectoryWarningDialog />
    </>
  )
}
