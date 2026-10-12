import { useState } from 'react'
import { Navigate } from 'react-router'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { DevLoginForm } from '../auth/DevLoginForm'
import { useAuthConfig } from '../auth/hooks'
import { AdminStep } from './AdminStep'
import { DirectoryStep } from './DirectoryStep'

/** 최초 설정 마법사(세션 불필요). 1단계 AD 서버 등록 → 2단계 첫 관리자 등록. */
export function SetupPage() {
  const config = useAuthConfig()
  const [reregister, setReregister] = useState(false)

  if (config.isPending) return <p className="content">불러오는 중…</p>
  if (config.isError) return <ErrorBanner error={config.error} />

  const { needs_directory_setup, needs_admin_setup, dev_login } = config.data
  if (!needs_directory_setup && !needs_admin_setup) return <Navigate to="/login" replace />

  // AD 서버가 아직 없으면 2단계는 없다. 있으면 "다시 등록"을 눌렀을 때만 1단계로 돌아간다.
  const stepOne = needs_directory_setup || reregister
  return (
    <main className="login">
      {stepOne ? (
        <DirectoryStep onSaved={() => setReregister(false)} />
      ) : (
        <AdminStep onBack={() => setReregister(true)} />
      )}
      {dev_login && <DevLoginForm />}
    </main>
  )
}
