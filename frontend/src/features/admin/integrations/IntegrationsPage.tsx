import '../admin.css'
import { DirectorySection } from './DirectorySection'
import { StorageSection } from './StorageSection'

/** 외부연동(`/admin/integrations`): AD(LDAP) 서버 설정과 파일 저장 위치. 관리자 전용. */
export function IntegrationsPage() {
  return (
    <section className="admin-page" aria-labelledby="integrations-title">
      <h2 id="integrations-title">외부연동</h2>
      <DirectorySection />
      <StorageSection />
    </section>
  )
}
