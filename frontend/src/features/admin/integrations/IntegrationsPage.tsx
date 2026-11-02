import { useAuthConfig } from '../../../data/auth'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import '../admin.css'
import { DirectorySection } from './DirectorySection'
import { StorageSection } from './StorageSection'

/**
 * 외부연동(`/admin/integrations`): AD(LDAP) 서버 설정과 파일 저장 위치. 관리자 전용.
 * 앱에서 계정을 직접 관리(local)하는 시스템은 AD를 쓰지 않으므로 AD 설정 대신 안내만 보인다(서버도 AD 설정 저장을 거절한다).
 */
export function IntegrationsPage() {
  const config = useAuthConfig()
  return (
    <section className="admin-page" aria-labelledby="integrations-title">
      <h2 id="integrations-title">외부연동</h2>
      <ErrorBanner error={config.error} />
      {config.isPending && <p className="hint">불러오는 중…</p>}
      {config.isSuccess &&
        (config.data.authMode === 'local' ? (
          <section className="admin-card" aria-labelledby="directory-local-title">
            <h3 id="directory-local-title">로그인 방식</h3>
            <p>이 시스템은 앱에서 계정을 직접 관리합니다. AD(LDAP) 서버 설정은 사용하지 않습니다.</p>
            <p className="hint">계정과 비밀번호는 사용자 관리에서 만들고 고칩니다.</p>
          </section>
        ) : (
          <DirectorySection />
        ))}
      <StorageSection />
    </section>
  )
}
