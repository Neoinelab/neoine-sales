import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { useSetupStatus } from '../../data/setup'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { AdminStep } from './AdminStep'
import { DirectoryStep } from './DirectoryStep'
import { StorageStep } from './StorageStep'
import { SetupSteps, type StepNo } from './SetupSteps'
import './setup.css'

/**
 * 최초 설정(`/setup`, 공개): ① AD 서버 → ② 파일 저장 위치 → ③ 관리자 등록. 순서는 서버 상태(SetupState)가 정한다.
 * 모두 끝난 상태로 열면 `/login`으로 보낸다.
 */
export function SetupPage() {
  const status = useSetupStatus()
  const navigate = useNavigate()
  const [back, setBack] = useState<StepNo | null>(null)
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
  if (adminDone && !registering) return <Navigate to="/login" replace />

  const derived: StepNo = !directoryDone ? 1 : !storageDone ? 2 : 3
  const step = back ?? derived
  return (
    <main className="setup">
      <h1>최초 설정</h1>
      <p className="hint">처음 한 번만 필요한 설정입니다. 순서대로 진행하세요.</p>
      <SetupSteps current={step} done={[directoryDone, storageDone, adminDone]} />
      {step === 1 && <DirectoryStep onSaved={() => setBack(null)} />}
      {step === 2 && <StorageStep onBack={() => setBack(1)} />}
      {step === 3 && (
        <AdminStep
          onBack={() => setBack(1)}
          onBusyChange={setRegistering}
          onRegistered={() => void navigate('/', { replace: true })}
        />
      )}
    </main>
  )
}
