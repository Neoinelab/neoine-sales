import { useState } from 'react'
import { useRegisterAdmin } from '../../data/setup'
import { errorFields } from '../../data/errorFields'
import type { AuthMode } from '../../shared/model/types'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { TextField } from '../../shared/ui/fields'

interface Props {
  /** 고른 인증 방식. local이면 계정 정보를 직접 받고, 그 밖에는 처음 로그인하는 AD 계정을 관리자로 올린다. */
  authMode: AuthMode | null
  /** 등록을 시작/끝냈을 때(페이지가 "이미 설정됨 → 로그인" 이동을 잠시 막는다). */
  onBusyChange: (busy: boolean) => void
  /** 등록과 로그인이 끝났을 때. */
  onRegistered: () => void
  onBack: () => void
}

const CONFIRM_MISMATCH = '비밀번호 확인이 일치하지 않습니다.'
const MISSING_PASSWORD = '비밀번호를 입력하세요.'

/** 3단계: 첫 관리자를 등록한다. 성공하면 그 계정으로 로그인된다. */
export function AdminStep({ authMode, onBusyChange, onRegistered, onBack }: Props) {
  const register = useRegisterAdmin()
  const local = authMode === 'local'
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [clientError, setClientError] = useState<string | null>(null)
  const invalid = errorFields(register.error)

  function submit() {
    if (local && password === '' && confirm === '') {
      setClientError(MISSING_PASSWORD)
      return
    }
    if (local && password !== confirm) {
      setClientError(CONFIRM_MISMATCH)
      return
    }
    setClientError(null)
    onBusyChange(true)
    register.mutate(
      local
        ? {
            loginId: loginId.trim(),
            password,
            profile: { name: name.trim(), email: email.trim() || null, phone: phone.trim() || null },
          }
        : { loginId, password },
      {
        onSuccess: onRegistered,
        onError: () => {
          setPassword('')
          setConfirm('')
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
      <p>{local ? '처음 등록하는 계정이 관리자가 됩니다. 아이디와 비밀번호는 이 앱에서 직접 관리합니다.' : '처음 등록하는 AD 계정이 관리자가 됩니다.'}</p>
      {clientError ? (
        <p role="alert" className="error">
          {clientError}
        </p>
      ) : (
        <ErrorBanner error={register.error} />
      )}
      <TextField
        label={local ? '아이디' : 'AD 아이디'}
        name="login_id"
        autoComplete="username"
        value={loginId}
        onChange={setLoginId}
        invalid={invalid.includes('login_id')}
      />
      <TextField
        label="비밀번호"
        name="password"
        type="password"
        autoComplete={local ? 'new-password' : 'current-password'}
        value={password}
        onChange={setPassword}
        invalid={invalid.includes('password')}
      />
      {local && (
        <>
          <TextField label="비밀번호 확인" name="password_confirm" type="password" autoComplete="new-password" value={confirm} onChange={setConfirm} />
          <TextField label="이름" name="display_name" autoComplete="name" value={name} onChange={setName} invalid={invalid.includes('display_name')} />
          <TextField label="이메일" name="email" type="email" autoComplete="email" value={email} onChange={setEmail} invalid={invalid.includes('email')} />
          <TextField label="전화번호" name="phone" type="tel" autoComplete="tel" value={phone} onChange={setPhone} invalid={invalid.includes('phone')} />
        </>
      )}
      <div className="actions">
        <button type="button" onClick={onBack}>
          인증 방식 다시 선택
        </button>
        <button type="submit" className="primary" disabled={register.isPending}>
          관리자 등록
        </button>
      </div>
    </form>
  )
}
