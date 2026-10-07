import { useState } from 'react'
import { Navigate, useSearchParams } from 'react-router'
import type { Schemas } from '../../shared/api/client'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { SelectField } from '../../shared/ui/fields'
import { useAuthConfig, useDevLogin, useMe } from './hooks'

const MESSAGES: Record<string, string> = {
  auth: '로그인에 실패했습니다. 다시 시도하세요.',
  denied: '이 시스템을 사용할 권한이 없습니다. 관리자에게 그룹 등록을 요청하세요.',
}

export function LoginPage() {
  const [params] = useSearchParams()
  const me = useMe()
  const config = useAuthConfig()
  const devLogin = useDevLogin()
  const [role, setRole] = useState<Schemas['Role']>('sales')

  if (me.data) return <Navigate to="/" replace />
  const failure = params.get('error')

  return (
    <main className="login">
      <h1>neoine-sales</h1>
      {failure && (
        <p role="alert" className="error">
          {MESSAGES[failure] ?? MESSAGES.auth}
        </p>
      )}
      <ErrorBanner error={config.error ?? devLogin.error} />
      {config.data?.oidc && (
        <a className="button primary" href="/api/v1/auth/login">
          회사 계정(AD)으로 로그인
        </a>
      )}
      {config.data?.dev_login && (
        <form
          className="panel"
          onSubmit={(e) => {
            e.preventDefault()
            devLogin.mutate(role)
          }}
        >
          <h2>개발용 로그인</h2>
          <p className="hint">로컬 환경에서만 보입니다.</p>
          <SelectField label="역할" name="role" value={role} onChange={(v) => setRole(v as Schemas['Role'])}>
            <option value="sales">sales</option>
            <option value="admin">admin</option>
          </SelectField>
          <button type="submit" className="primary">
            개발용으로 로그인
          </button>
        </form>
      )}
    </main>
  )
}
