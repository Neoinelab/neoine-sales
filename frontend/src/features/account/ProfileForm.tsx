import { useState } from 'react'
import { useUpdateMyProfile } from '../../data/me'
import { errorFields } from '../../data/errorFields'
import type { MyProfile, ProfileChange } from '../../shared/model/types'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { TextField } from '../../shared/ui/fields'
import { Notice } from '../../shared/ui/Notice'

interface Values {
  name: string
  email: string
  phone: string
}

const valuesOf = (p: MyProfile): Values => ({ name: p.name, email: p.email ?? '', phone: p.phone ?? '' })

/** 바뀐 칸만 담는다. 수정할 수 없는 칸은 건드리지 않고, 비운 이메일·전화는 null(이름은 비울 수 없어 서버가 거절한다). */
function changeOf(profile: MyProfile, values: Values): ProfileChange {
  const change: ProfileChange = {}
  const name = values.name.trim()
  const email = values.email.trim()
  const phone = values.phone.trim()
  if (profile.editable.name && name !== profile.name) change.name = name
  if (profile.editable.email && email !== (profile.email ?? '')) change.email = email === '' ? null : email
  if (profile.editable.phone && phone !== (profile.phone ?? '')) change.phone = phone === '' ? null : phone
  return change
}

/** 아이디·역할(읽기 전용)과 이름·이메일·전화번호. 서버의 검증 문구를 그대로 보여 주고 입력은 유지한다. */
export function ProfileForm({ profile }: { profile: MyProfile }) {
  const update = useUpdateMyProfile()
  const [values, setValues] = useState<Values>(() => valuesOf(profile))
  const [saved, setSaved] = useState(false)
  const change = changeOf(profile, values)
  const dirty = Object.keys(change).length > 0
  const invalid = errorFields(update.error)
  const set = (key: keyof Values) => (value: string) => {
    setSaved(false)
    setValues((v) => ({ ...v, [key]: value }))
  }

  function submit() {
    setSaved(false)
    update.mutate(change, {
      onSuccess: (next) => {
        setValues(valuesOf(next))
        setSaved(true)
      },
    })
  }

  return (
    <form
      className="account-card"
      aria-label="기본 정보"
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
    >
      <h3>기본 정보</h3>
      <ErrorBanner error={update.error} />
      {saved && <Notice kind="success" onClose={() => setSaved(false)}>저장했습니다.</Notice>}
      {!profile.editable.name && <p className="hint">이름·이메일은 AD에서 관리합니다. 전화번호만 고칠 수 있습니다.</p>}
      <TextField label="아이디" name="login_id" value={profile.loginId} onChange={() => undefined} readOnly />
      <TextField label="역할" name="role" value={profile.role} onChange={() => undefined} readOnly />
      <TextField label="이름" name="display_name" autoComplete="name" value={values.name} onChange={set('name')} disabled={!profile.editable.name} invalid={invalid.includes('display_name')} />
      <TextField label="이메일" name="email" type="email" autoComplete="email" value={values.email} onChange={set('email')} disabled={!profile.editable.email} invalid={invalid.includes('email')} />
      <TextField label="전화번호" name="phone" type="tel" autoComplete="tel" value={values.phone} onChange={set('phone')} disabled={!profile.editable.phone} invalid={invalid.includes('phone')} />
      <div className="actions">
        <button type="submit" className="primary" disabled={!dirty || update.isPending}>
          저장
        </button>
      </div>
    </form>
  )
}
