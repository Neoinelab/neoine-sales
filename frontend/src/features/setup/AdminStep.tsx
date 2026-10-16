import { useState } from 'react'
import { useRegisterAdmin } from '../../data/setup'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { TextField } from '../../shared/ui/fields'

interface Props {
  /** 등록을 시작/끝냈을 때(페이지가 "이미 설정됨 → 로그인" 이동을 잠시 막는다). */
  onBusyChange: (busy: boolean) => void
  /** 등록과 로그인이 끝났을 때. */
  onRegistered: () => void
  onBack: () => void
}

/** 3단계: 처음 로그인하는 AD 계정을 관리자로 등록한다. 성공하면 그 계정으로 로그인된다. */
export function AdminStep({ onBusyChange, onRegistered, onBack }: Props) {
  const register = useRegisterAdmin()
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')

  function submit() {
    onBusyChange(true)
    register.mutate(
      { loginId, password },
      {
        onSuccess: onRegistered,
        onError: () => {
          setPassword('')
          onBusyChange(false)
        },
      },
    )
  }

  return (
    <form
      className="setup-card"
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
    >
      <h2>관리자 등록</h2>
      <p>처음 등록하는 AD 계정이 관리자가 됩니다.</p>
      <ErrorBanner error={register.error} />
      <TextField label="AD 아이디" name="login_id" autoComplete="username" value={loginId} onChange={setLoginId} />
      <TextField
        label="비밀번호"
        name="password"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={setPassword}
      />
      <div className="actions">
        <button type="button" onClick={onBack}>
          AD 서버 다시 등록
        </button>
        <button type="submit" className="primary" disabled={register.isPending}>
          관리자 등록
        </button>
      </div>
    </form>
  )
}
