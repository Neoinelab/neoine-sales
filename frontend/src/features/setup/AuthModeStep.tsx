import { useChooseAuthMode } from '../../data/setup'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'

interface Props {
  /** "AD 연동": 서버를 부르지 않고 AD 서버 등록 폼으로 간다(AD 서버를 저장하면 방식이 AD로 기록된다). */
  onChooseAd: () => void
  /** "앱에서 직접 관리"가 서버에 기록된 뒤(단계 상태가 갱신된 다음). */
  onChosenLocal: () => void
}

/** 1단계: 로그인 방식. 회사 AD로 로그인하거나, 앱에서 계정과 비밀번호를 직접 관리한다. 관리자가 생기기 전까지 다시 고를 수 있다. */
export function AuthModeStep({ onChooseAd, onChosenLocal }: Props) {
  const choose = useChooseAuthMode()
  return (
    <section className="setup-card" aria-labelledby="auth-mode-title">
      <h2 id="auth-mode-title">인증 방식</h2>
      <p className="hint">사용자가 로그인하는 방법을 고릅니다. 관리자를 등록하기 전까지 다시 고를 수 있습니다.</p>
      <ErrorBanner error={choose.error} />
      <div className="actions">
        <button type="button" disabled={choose.isPending} onClick={onChooseAd}>
          AD 연동
        </button>
        <button
          type="button"
          className="primary"
          disabled={choose.isPending}
          onClick={() => choose.mutate('local', { onSuccess: onChosenLocal })}
        >
          앱에서 직접 관리
        </button>
      </div>
      <p className="hint">AD 연동: 회사 AD(LDAP) 계정과 비밀번호로 로그인합니다. 앱에서 직접 관리: 관리자가 앱에서 계정을 만들고 비밀번호를 정합니다.</p>
    </section>
  )
}
