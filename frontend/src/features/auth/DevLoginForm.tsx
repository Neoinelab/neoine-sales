import { useState } from 'react'
import type { Schemas } from '../../shared/api/client'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { SelectField } from '../../shared/ui/fields'
import { useDevLogin } from './hooks'

/** 서버가 허용할 때만 쓰는 개발용 로그인(로그인 화면과 최초 설정 마법사 공통). */
export function DevLoginForm() {
  const devLogin = useDevLogin()
  const [role, setRole] = useState<Schemas['Role']>('sales')
  return (
    <form
      className="panel"
      onSubmit={(e) => {
        e.preventDefault()
        devLogin.mutate(role)
      }}
    >
      <h2>개발용 로그인</h2>
      <p className="hint">로컬 환경에서만 보입니다.</p>
      <ErrorBanner error={devLogin.error} />
      <SelectField label="역할" name="role" value={role} onChange={(v) => setRole(v as Schemas['Role'])}>
        <option value="admin">admin</option>
        <option value="sales">sales</option>
        <option value="user">user</option>
      </SelectField>
      <button type="submit" className="primary">
        개발용으로 로그인
      </button>
    </form>
  )
}
