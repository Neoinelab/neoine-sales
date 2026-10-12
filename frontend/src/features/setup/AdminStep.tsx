import { CredentialsForm } from '../auth/CredentialsForm'
import { useSetupAdmin } from '../auth/hooks'
import { authErrorMessage } from '../auth/messages'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'

/** 마법사 2단계: 처음 로그인하는 AD 계정을 관리자로 등록한다. */
export function AdminStep({ onBack }: { onBack: () => void }) {
  const setup = useSetupAdmin()
  return (
    <div className="panel">
      <h1>관리자 등록</h1>
      <p>처음 등록하는 AD 계정이 관리자가 됩니다.</p>
      <ErrorBanner error={setup.error} format={authErrorMessage} />
      <CredentialsForm submitLabel="관리자 등록" pending={setup.isPending} onSubmit={setup.mutateAsync} />
      <button type="button" onClick={onBack}>
        AD 서버 다시 등록
      </button>
    </div>
  )
}
