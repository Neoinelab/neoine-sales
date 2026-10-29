import type { DirectorySettings, DirectorySecurity, DirectorySettingsInput } from '../model/types'

/** 설정 화면에서 저장된 바인드 비밀번호를 대신 보이는 고정 마스크(실제 비밀번호와 길이가 무관하다). */
export const BIND_PASSWORD_MASK = '********'

/** 보안 연결 방식별 기본 포트. */
export const DEFAULT_PORTS: Readonly<Record<DirectorySecurity, number>> = { none: 389, ssl: 636, starttls: 389 }

/** 저장된 접속 정보. 서버나 계정이 바뀌었는지 비교하는 데만 쓴다(내부용). */
interface SavedEndpoint {
  host: string
  port: string
  security: DirectorySecurity
  bindAccount: string
  /** 저장된 비밀번호를 읽을 수 없다(다시 입력해야 한다). */
  unreadable: boolean
}

/** 폼 입력 상태. 숫자는 입력 중 상태를 위해 문자열로 둔다. Base DN은 읽기 전용이라 여기에 없다. */
export interface DirectoryFormValues {
  host: string
  port: string
  security: DirectorySecurity
  bindAccount: string
  /** 입력 값 또는 마스크. 마스크를 비밀번호로 보내지 않도록 전송 여부는 `bindPasswordTouched`로만 정한다. */
  bindPassword: string
  /** 사용자가 비밀번호를 직접 입력했거나 다시 입력해야 한다. false이면 저장된 비밀번호를 유지한다. */
  bindPasswordTouched: boolean
  /** 서버나 계정을 바꿔 비밀번호 칸을 비웠다(안내 문구용). */
  retypeBindPassword: boolean
  userFilter: string
  connectTimeoutSeconds: string
  /** 설정 화면에서만 있다. 최초 등록 폼은 null. */
  saved: SavedEndpoint | null
}

export const DEFAULT_DIRECTORY_FORM: DirectoryFormValues = {
  host: '',
  port: String(DEFAULT_PORTS.ssl),
  security: 'ssl',
  bindAccount: '',
  bindPassword: '',
  bindPasswordTouched: true,
  retypeBindPassword: false,
  userFilter: '(&(objectClass=user)(sAMAccountName={login_id}))',
  connectTimeoutSeconds: '5',
  saved: null,
}

/** 저장된 AD 설정 → 입력 칸 값. 비밀번호는 마스크로만 보이고, 읽을 수 없으면 빈 칸으로 다시 입력을 요구한다. */
export function formFromDirectory(s: DirectorySettings): DirectoryFormValues {
  const unreadable = s.bindCredentialStatus === 'unreadable'
  return {
    host: s.host,
    port: String(s.port),
    security: s.security,
    bindAccount: s.bindAccount,
    bindPassword: unreadable ? '' : BIND_PASSWORD_MASK,
    bindPasswordTouched: unreadable,
    retypeBindPassword: false,
    userFilter: s.userFilter,
    connectTimeoutSeconds: String(s.connectTimeoutSeconds),
    saved: { host: s.host, port: String(s.port), security: s.security, bindAccount: s.bindAccount, unreadable },
  }
}

/** 입력 칸 값 → 게이트웨이 입력. 손대지 않은 비밀번호는 null(저장 값 유지)이다. */
export function inputFromForm(v: DirectoryFormValues): DirectorySettingsInput {
  return {
    host: v.host,
    port: Number(v.port),
    security: v.security,
    bindAccount: v.bindAccount,
    bindPassword: v.bindPasswordTouched ? v.bindPassword : null,
    userFilter: v.userFilter,
    connectTimeoutSeconds: Number(v.connectTimeoutSeconds),
  }
}

/** 보안 연결 방식을 바꾼다. 포트가 비었거나 이전 방식의 기본 포트이면 새 방식의 기본 포트로 바꾸고, 직접 쓴 포트는 둔다. */
export function changeSecurity(values: DirectoryFormValues, mode: DirectorySecurity): DirectoryFormValues {
  const keepPort = values.port.trim() !== '' && values.port !== String(DEFAULT_PORTS[values.security])
  return { ...values, security: mode, port: keepPort ? values.port : String(DEFAULT_PORTS[mode]) }
}

type EndpointField = 'host' | 'port' | 'security' | 'bindAccount'

function sameEndpoint(values: DirectoryFormValues, saved: SavedEndpoint): boolean {
  return (
    values.host === saved.host &&
    values.port === saved.port &&
    values.security === saved.security &&
    values.bindAccount === saved.bindAccount
  )
}

/**
 * 호스트·포트·보안 연결·바인드 계정 중 하나를 바꾼다. 저장된 설정에서 이 값들이 달라지면(비밀번호를 아직 직접 입력하지 않았다면)
 * 마스크를 비우고 다시 입력을 요구한다. 저장된 값으로 되돌리면 마스크를 되돌린다.
 */
export function changeEndpointField(values: DirectoryFormValues, field: EndpointField, value: string): DirectoryFormValues {
  const next = field === 'security' ? changeSecurity(values, value as DirectorySecurity) : { ...values, [field]: value }
  const { saved } = next
  if (saved === null) return next
  if (!next.bindPasswordTouched && !sameEndpoint(next, saved)) {
    return { ...next, bindPassword: '', bindPasswordTouched: true, retypeBindPassword: true }
  }
  if (next.retypeBindPassword && next.bindPassword === '' && sameEndpoint(next, saved)) {
    return { ...next, bindPassword: BIND_PASSWORD_MASK, bindPasswordTouched: false, retypeBindPassword: false }
  }
  return next
}

/** 비밀번호 칸에 값을 입력한다(입력한 순간부터 이 값을 보낸다). */
export function typeBindPassword(values: DirectoryFormValues, text: string): DirectoryFormValues {
  return { ...values, bindPassword: text, bindPasswordTouched: true }
}

/** 마스크가 보이는 칸을 쓰기 시작하면 마스크를 비운다. */
export function focusBindPassword(values: DirectoryFormValues): DirectoryFormValues {
  if (values.bindPasswordTouched) return values
  return { ...values, bindPassword: '', bindPasswordTouched: true }
}

/** 아무것도 입력하지 않고 칸을 떠나면 저장된 비밀번호 유지(마스크)로 되돌린다. 다시 입력해야 하는 경우는 그대로 둔다. */
export function blurBindPassword(values: DirectoryFormValues): DirectoryFormValues {
  const { saved } = values
  if (saved === null || saved.unreadable || values.retypeBindPassword || values.bindPassword !== '') return values
  return { ...values, bindPassword: BIND_PASSWORD_MASK, bindPasswordTouched: false }
}

/** 요청이 끝나면 입력한 비밀번호를 화면에서 지운다: 저장된 값을 유지하는 상태면 마스크로, 아니면 빈 칸으로. */
export function clearTypedBindPassword(values: DirectoryFormValues): DirectoryFormValues {
  const { saved } = values
  if (saved !== null && !saved.unreadable && !values.retypeBindPassword) {
    return { ...values, bindPassword: BIND_PASSWORD_MASK, bindPasswordTouched: false }
  }
  return { ...values, bindPassword: '', bindPasswordTouched: true }
}

/** 서버로 보내기 전에 화면에서 막는 유일한 검증: 보내야 하는 바인드 비밀번호가 비었는지. 나머지는 서버 검증을 보인다. */
export function validateForm(values: DirectoryFormValues, mode: 'setup' | 'settings'): string | null {
  const mustType = mode === 'setup' || values.bindPasswordTouched
  if (mustType && values.bindPassword.trim() === '') return '바인드 비밀번호를 입력하세요'
  return null
}
