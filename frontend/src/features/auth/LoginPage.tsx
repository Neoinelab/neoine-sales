import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router'
import { useAuthConfig, useLogin, useMe, useQuickLogin } from '../../data/auth'
import { QUICK_LOGIN_USERS } from '../../shared/model/constants'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { TextField } from '../../shared/ui/fields'

/**
 * 로그인: 아이디 + 비밀번호, 서버가 개발용 로그인을 켠 경우에만 빠른 로그인 버튼(`config.quickLogin`).
 * 오류 문구는 게이트웨이(서버)가 준다.
 * 서버 설정을 읽은 뒤에 그린다(설정을 못 읽어도 로그인 폼은 오류 문구와 함께 보인다).
 */
export function LoginPage() {
  const me = useMe()
  const config = useAuthConfig()
  const navigate = useNavigate()
  const login = useLogin()
  const quick = useQuickLogin()
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')

  if (me.data) return <Navigate to="/" replace />
  if (config.isPending) {
    return (
      <main className="login">
        <p className="hint">불러오는 중…</p>
      </main>
    )
  }

  // 최초 설정이 끝나지 않았으면 로그인할 수 없다. 개발용 빠른 로그인이 켜져 있으면 그 길을 막지 않도록 안내 링크만 둔다.
  if (config.data?.needsSetup && !config.data.quickLogin) return <Navigate to="/setup" replace />

  const submit = () => {
    login
      .mutateAsync({ loginId: loginId.trim(), password })
      .then(() => navigate('/'))
      .catch(() => setPassword(''))
  }

  return (
    <main className="login">
      <h1>neoine-sales</h1>
      <ErrorBanner error={login.error ?? quick.error ?? config.error} />
      {config.data?.needsSetup && (
        <p className="hint">
          최초 설정이 끝나지 않았습니다. <Link to="/setup">최초 설정으로 이동</Link>
        </p>
      )}
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
      {config.data?.quickLogin && (
        <section className="panel" aria-label="빠른 로그인">
          <h2>빠른 로그인</h2>
          <div className="actions">
            {QUICK_LOGIN_USERS.map((user) => (
              <button
                key={user.userId}
                type="button"
                disabled={quick.isPending}
                onClick={() => quick.mutate(user.userId, { onSuccess: () => void navigate('/') })}
              >
                {user.label}
              </button>
            ))}
          </div>
        </section>
      )}
    </main>
  )
}
