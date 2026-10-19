import { useState } from 'react'
import { useContactCompanies, useContactsByCompany } from '../../data/contacts'
import {
  findSamePerson,
  validateContactInput,
  WHITESPACE_MESSAGE,
  type ContactFieldErrors,
} from '../model/contactRules'
import type { ContactDraft } from '../model/inputs'
import type { ContactKind, ContactRow } from '../model/types'
import { ComboBox, type ComboOption } from '../ui/ComboBox'
import { PickerField } from './PickerField'
import { useWhitespaceGuard } from './useWhitespaceGuard'
import '../ui/kvGrid.css'
import './contact.css'

export interface ContactPickerProps {
  kind: ContactKind
  /** 화면 표시용 접두어('고객' | '파트너'). 입력 라벨이 "<label> 회사명"처럼 된다. */
  label: string
  value: ContactDraft
  onChange: (next: ContactDraft) => void
  /** 폼이 정한 필드별 오류(제출 검증). 입력 아래 role=alert로 보인다. */
  errors?: ContactFieldErrors
  /** 이 연락처가 이미 현재 Deal에 연결돼 있으면 true(공유 안내 기준이 1건 더 높아진다). */
  linkedHere?: boolean
  /** 회사명을 목록에서 골랐을 때만 호출(직접 입력은 제외). 호출처가 담당자 입력으로 포커스를 옮기는 데 쓴다. */
  onCompanySelect?: (company: string) => void
  /** 담당자를 목록에서 골랐을 때만 호출(연락 정보가 채워진 결과를 넘긴다). */
  onPersonSelect?: (next: ContactDraft) => void
  /** 'stack'(기본): 테두리 fieldset에 라벨 전체 글자. 'rows': 라벨-값 한 줄 행(보이는 라벨은 짧게, 접근성 이름은 그대로). */
  layout?: 'stack' | 'rows'
}

const EMPTY_FIELDS = { title: '', email: null, phone: null } as const

function optionOf(row: ContactRow): ComboOption {
  const detail = [row.title, row.email].filter(Boolean).join(' · ')
  return { id: row.id, value: row.name, description: detail || undefined }
}

/**
 * 연락처(명함) 선택·입력: ①회사명(목록 선택 또는 직접 입력) → ②담당자(그 회사의 목록 선택 또는 직접 입력)
 * → ③직급/이메일/전화(기존 선택 시 자동 입력, 고치면 contactId를 유지해 저장 시 연락처 갱신, 신규는 contactId null).
 * 회사명·담당자명·이메일·전화는 공백 입력을 막는다(직급은 허용). 저장은 호출처가 ContactDraft로 한다.
 */
export function ContactPicker({ kind, label, value, onChange, errors, linkedHere = false, onCompanySelect, onPersonSelect, layout = 'stack' }: ContactPickerProps) {
  const companies = useContactCompanies(kind).data ?? []
  const rows = useContactsByCompany(kind, value.company).data ?? []
  const { flashed, guard } = useWhitespaceGuard()
  const [emailTouched, setEmailTouched] = useState(false)

  const selected = value.contactId ? rows.find((r) => r.id === value.contactId) : undefined
  const flash = (field: string) => (flashed[field] ? WHITESPACE_MESSAGE : undefined)
  const emailFormat = emailTouched && value.email ? validateContactInput({ ...value, title: value.title }).email : undefined

  function changeCompany(company: string) {
    const sameCompany = company.toLowerCase() === value.company.toLowerCase()
    if (!sameCompany && value.contactId !== null) {
      onChange({ contactId: null, company, name: '', ...EMPTY_FIELDS })
    } else {
      onChange({ ...value, company })
    }
  }

  function changeName(name: string) {
    const renamed = selected !== undefined && selected.name.toLowerCase() !== name.toLowerCase()
    onChange({ ...value, name, contactId: renamed ? null : value.contactId })
  }

  function selectPerson(option: ComboOption) {
    const row = rows.find((r) => r.id === option.id)
    if (!row) return
    const next: ContactDraft = {
      contactId: row.id,
      company: row.company,
      name: row.name,
      title: row.title,
      email: row.email,
      phone: row.phone,
    }
    onChange(next)
    onPersonSelect?.(next)
  }

  const sameAsExisting =
    value.contactId === null &&
    !value.email &&
    value.company !== '' &&
    value.name !== '' &&
    findSamePerson(rows, kind, { ...value, email: null }) !== null

  const sharedCount = selected && selected.dealCount >= (linkedHere ? 2 : 1) ? selected.dealCount : 0

  const asRows = layout === 'rows'
  const visible = (short: string) => (asRows ? { visibleLabel: short } : {})

  const fields = (
    <>
      <ComboBox
        {...visible('회사')}
        label={`${label} 회사명`}
        name={`${kind}Company`}
        value={value.company}
        onChange={changeCompany}
        options={companies.map((c) => ({ value: c }))}
        onSelectOption={onCompanySelect ? (option) => onCompanySelect(option.value) : undefined}
        transform={(raw) => guard('company', raw)}
        error={errors?.company}
        hint={flash('company')}
      />
      <ComboBox
        {...visible('담당자')}
        label={`${label} 담당자명`}
        name={`${kind}Name`}
        value={value.name}
        onChange={changeName}
        options={rows.map(optionOf)}
        onSelectOption={selectPerson}
        transform={(raw) => guard('name', raw)}
        error={errors?.name}
        hint={flash('name')}
      />
      <PickerField {...visible('직급')} label={`${label} 직급`} name={`${kind}Title`} value={value.title} error={errors?.title} onChange={(title) => onChange({ ...value, title })} />
      <PickerField
        {...visible('이메일')}
        label={`${label} 이메일`}
        name={`${kind}Email`}
        inputMode="email"
        value={value.email ?? ''}
        error={errors?.email ?? emailFormat}
        hint={flash('email')}
        onBlur={() => setEmailTouched(true)}
        onChange={(raw) => onChange({ ...value, email: guard('email', raw) || null })}
      />
      <PickerField
        {...visible('전화')}
        label={`${label} 전화`}
        name={`${kind}Phone`}
        inputMode="tel"
        value={value.phone ?? ''}
        error={errors?.phone}
        hint={flash('phone')}
        onChange={(raw) => onChange({ ...value, phone: guard('phone', raw) || null })}
      />
      {sameAsExisting && (
        <p className="field-hint">기존 연락처와 같은 사람으로 처리됩니다(회사명·담당자명 일치, 이메일 없음).</p>
      )}
      {sharedCount > 0 && (
        <p className="field-hint">이 연락처는 {sharedCount}개 Deal에서 함께 사용 중입니다. 수정하면 모두에 반영됩니다.</p>
      )}
    </>
  )

  if (asRows) {
    return (
      <fieldset className="contact-picker contact-picker--rows">
        <legend className="kv-visually-hidden">{label}</legend>
        <div className="kv-grid">{fields}</div>
      </fieldset>
    )
  }
  return (
    <fieldset className="contact-picker">
      <legend>{label}</legend>
      {fields}
    </fieldset>
  )
}
