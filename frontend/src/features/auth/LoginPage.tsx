import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { useAuthConfig, useLogin, useMe } from '../../data/auth'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { TextField } from '../../shared/ui/fields'

/**
 * 로그인: 아이디 + 비밀번호, 최초 설정이 필요하면 `/setup`으로 보낸다.
 * 오류 문구는 게이트웨이(서버)가 준다.
 * 서버 설정을 읽은 뒤에 그린다(설정을 못 읽어도 로그인 폼은 오류 문구와 함께 보인다).
 */
export function LoginPage() {
  const me = useMe()
  const config = useAuthConfig()
  const navigate = useNavigate()
  const login = useLogin()
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')

  if (config.isPending) {
    return (
      <main className="login">
        <p className="hint">불러오는 중…</p>
      </main>
    )
  }

  // 최초 설정이 끝나지 않았으면 로그인할 수 없으므로 항상 설정 화면으로 보낸다.
  if (config.data?.needsSetup) return <Navigate to="/setup" replace />
  if (me.data) return <Navigate to="/" replace />

  const submit = () => {
    login
      .mutateAsync({ loginId: loginId.trim(), password })
      .then(() => navigate('/'))
      .catch(() => setPassword(''))
  }

  return (
    <main className="login">
      <h1>
        <img src="/images/salesX.png" alt="salesX" width={2172} height={724} />
      </h1>
      <ErrorBanner error={login.error ?? config.error} />
      <form
        className="panel"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <TextField label="아이디" name="login_id" autoComplete="username" value={loginId} onChange={setLoginId} />
        <TextField
          label="비밀번호"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={setPassword}
        />
        <button type="submit" className="primary" disabled={login.isPending}>
          로그인
        </button>
      </form>
    </main>
  )
}
