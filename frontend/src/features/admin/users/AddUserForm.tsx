import { useState } from 'react'
import { useCreateUser } from '../../../data/users'
import { errorFields } from '../../../data/errorFields'
import type { Role } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { SelectField, TextField } from '../../../shared/ui/fields'

const MISSING_AD = 'AD 아이디와 이름을 입력하세요.'
const MISSING_LOCAL = '아이디, 비밀번호, 이름을 입력하세요.'
const CONFIRM_MISMATCH = '비밀번호 확인이 일치하지 않습니다.'

/**
 * 사용자 등록. AD 연동 모드는 로그인을 허용할 AD 계정을 이름·역할(이메일·전화 선택)과 함께 등록하고 비밀번호는 AD가 확인한다.
 * 앱에서 직접 관리(local) 모드는 아이디·비밀번호·이름이 필수이고 이메일·전화는 선택이다. 비밀번호 정책 검증은 서버가 한다.
 */
export function AddUserForm({ local }: { local: boolean }) {
  const create = useCreateUser()
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [role, setRole] = useState<Role>('sales')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)
  const invalid = errorFields(error)

  function submit() {
    const missing = loginId.trim() === '' || name.trim() === '' || (local && password === '')
    if (missing) {
      setMessage(local ? MISSING_LOCAL : MISSING_AD)
      return
    }
    if (local && password !== confirm) {
      setMessage(CONFIRM_MISMATCH)
      return
    }
    setMessage(null)
    setError(null)
    create.mutate(
      {
        loginId: loginId.trim(),
        name: name.trim(),
        role,
        ...(local ? { password } : {}),
        email: email.trim() || null,
        phone: phone.trim() || null,
      },
      {
        onSuccess: () => {
          setLoginId('')
          setPassword('')
          setConfirm('')
          setName('')
          setEmail('')
          setPhone('')
          create.reset()
        },
        onError: (e) => {
          setPassword('')
          setConfirm('')
          setError(e)
          create.reset()
        },
      },
    )
  }

  return (
    <form
      className="admin-card"
      aria-label="사용자 등록"
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
    >
      <h3>사용자 등록</h3>
      {message ? (
        <p role="alert" className="error">
          {message}
        </p>
      ) : (
        <ErrorBanner error={error} />
      )}
      <div className="admin-form-row">
        <TextField label={local ? '아이디' : 'AD 아이디'} name="login_id" autoComplete="off" value={loginId} onChange={setLoginId} invalid={invalid.includes('login_id')} />
        {local && (
          <>
            <TextField label="비밀번호" name="password" type="password" autoComplete="new-password" value={password} onChange={setPassword} invalid={invalid.includes('password')} />
            <TextField label="비밀번호 확인" name="password_confirm" type="password" autoComplete="new-password" value={confirm} onChange={setConfirm} />
          </>
        )}
        <TextField label="이름" name="name" value={name} onChange={setName} invalid={invalid.includes('display_name')} />
        <TextField label="이메일" name="email" type="email" value={email} onChange={setEmail} invalid={invalid.includes('email')} />
        <TextField label="전화번호" name="phone" type="tel" value={phone} onChange={setPhone} invalid={invalid.includes('phone')} />
        <SelectField label="역할" name="role" value={role} onChange={(v) => setRole(v as Role)}>
          <option value="admin">admin</option>
          <option value="sales">sales</option>
          <option value="user">user</option>
        </SelectField>
        <button type="submit" className="primary" disabled={create.isPending}>
          추가
        </button>
      </div>
    </form>
  )
}
