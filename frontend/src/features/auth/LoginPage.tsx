import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { useLogin, useMe, useQuickLogin } from '../../data/auth'
import { QUICK_LOGIN_USERS } from '../../shared/model/constants'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { TextField } from '../../shared/ui/fields'

/** 목업 로그인(계획 6.1): 아이디 + 아무 비밀번호, 그리고 빠른 로그인 4버튼. 오류 문구는 게이트웨이가 준다. */
export function LoginPage() {
  const me = useMe()
  const navigate = useNavigate()
  const login = useLogin()
  const quick = useQuickLogin()
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')

  if (me.data) return <Navigate to="/" replace />

  const submit = () => {
    login
      .mutateAsync({ loginId: loginId.trim(), password })
      .then(() => navigate('/'))
      .catch(() => setPassword(''))
  }

  return (
    <main className="login">
      <h1>neoine-sales</h1>
      <ErrorBanner error={login.error ?? quick.error} />
      <form
        className="panel"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <TextField label="아이디" name="login_id" value={loginId} onChange={setLoginId} />
        <TextField label="비밀번호" name="password" type="password" value={password} onChange={setPassword} />
        <button type="submit" className="primary" disabled={login.isPending}>
          로그인
        </button>
        <p className="hint">목업이라 아무 비밀번호나 입력해도 됩니다.</p>
      </form>
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
    </main>
  )
}
