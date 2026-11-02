import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { useSetupStatus } from '../../data/setup'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { AdminStep } from './AdminStep'
import { AuthModeStep } from './AuthModeStep'
import { DirectoryStep } from './DirectoryStep'
import { StorageStep } from './StorageStep'
import { SetupSteps, type StepNo } from './SetupSteps'
import './setup.css'

/** 1단계 안의 두 화면: 방식을 고르는 화면과 AD 서버 등록 폼. */
type FirstView = 'choice' | 'ad'

/**
 * 최초 설정(`/setup`, 공개): ① 인증 방식(AD 연동이면 AD 서버 등록까지) → ② 파일 저장 위치 → ③ 관리자 등록.
 * 순서는 서버 상태(SetupState)가 정하고, 사용자가 되돌아가거나 "AD 연동"을 눌러 폼을 연 것만 화면 상태(`override`)로 둔다.
 * 모두 끝난 상태로 열면 `/login`으로 보낸다.
 */
export function SetupPage() {
  const status = useSetupStatus()
  const navigate = useNavigate()
  const [override, setOverride] = useState<FirstView | null>(null)
  const [registering, setRegistering] = useState(false)

  if (status.isPending) return <main className="setup"><p className="hint">불러오는 중…</p></main>
  if (status.isError) {
    return (
      <main className="setup">
        <h1>최초 설정</h1>
        <ErrorBanner error={status.error} />
      </main>
    )
  }

  const { directoryDone, storageDone, adminDone } = status.data
  // authMode가 아예 없는 응답은 AD 단계 여부(directoryDone)만 따른다. 서버는 항상 값 또는 null을 준다.
  const { authMode } = status.data
  if (adminDone && !registering) return <Navigate to="/login" replace />

  // 방식을 아직 안 골랐으면 선택 화면, AD인데 AD 서버가 없으면 AD 폼, 그 밖에는 저장 위치 → 관리자 등록.
  const derived: FirstView | 2 | 3 =
    authMode === null ? 'choice' : !directoryDone ? 'ad' : !storageDone ? 2 : 3
  const view = override ?? derived
  const step: StepNo = view === 'choice' || view === 'ad' ? 1 : view
  const backToChoice = () => setOverride('choice')
  return (
    <main className="setup">
      <h1>최초 설정</h1>
      <p className="hint">처음 한 번만 필요한 설정입니다. 순서대로 진행하세요.</p>
      <SetupSteps current={step} done={[authMode !== null && directoryDone, storageDone, adminDone]} />
      {view === 'choice' && <AuthModeStep onChooseAd={() => setOverride('ad')} onChosenLocal={() => setOverride(null)} />}
      {view === 'ad' && <DirectoryStep onSaved={() => setOverride(null)} onBack={backToChoice} />}
      {view === 2 && <StorageStep onBack={backToChoice} />}
      {view === 3 && (
        <AdminStep
          authMode={authMode ?? null}
          onBack={backToChoice}
          onBusyChange={setRegistering}
          onRegistered={() => void navigate('/', { replace: true })}
        />
      )}
    </main>
  )
}
