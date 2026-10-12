import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { useMe } from '../auth/hooks'
import { useDirectorySettings } from './hooks'
import { SettingsForm } from './SettingsForm'

/** 관리자 전용: 로그인에 쓰는 AD 서버 설정. */
export function SettingsPage() {
  const settings = useDirectorySettings()
  const me = useMe()
  return (
    <section>
      <div className="heading">
        <h1>AD 서버 설정</h1>
      </div>
      <ErrorBanner error={settings.error} />
      {(settings.isPending || me.isPending) && <p>불러오는 중…</p>}
      {settings.data && me.data && (
        <SettingsForm initial={settings.data} needsPassword={!me.data.subject.startsWith('dev:')} />
      )}
    </section>
  )
}
