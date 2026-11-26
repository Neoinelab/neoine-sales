import type { DirectorySettings, DirectorySecurity, DirectorySettingsInput } from '../model/types'

export const DEFAULT_PORTS: Readonly<Record<DirectorySecurity, number>> = { none: 389, ssl: 636, starttls: 389 }

export interface DirectoryFormValues {
  host: string
  port: string
  security: DirectorySecurity
  userFilter: string
  connectTimeoutSeconds: string
}

export const DEFAULT_DIRECTORY_FORM: DirectoryFormValues = {
  host: '', port: '636', security: 'ssl',
  userFilter: '(&(objectClass=user)(sAMAccountName={login_id}))', connectTimeoutSeconds: '5',
}

export function formFromDirectory(s: DirectorySettings): DirectoryFormValues {
  return { host: s.host, port: String(s.port), security: s.security, userFilter: s.userFilter, connectTimeoutSeconds: String(s.connectTimeoutSeconds) }
}

export function inputFromForm(v: DirectoryFormValues): DirectorySettingsInput {
  return { host: v.host, port: Number(v.port), security: v.security, userFilter: v.userFilter, connectTimeoutSeconds: Number(v.connectTimeoutSeconds) }
}

export function changeSecurity(values: DirectoryFormValues, mode: DirectorySecurity): DirectoryFormValues {
  const keepPort = values.port.trim() !== '' && values.port !== String(DEFAULT_PORTS[values.security])
  return { ...values, security: mode, port: keepPort ? values.port : String(DEFAULT_PORTS[mode]) }
}

export function validateForm(values: DirectoryFormValues): string | null {
  if (!values.host.trim()) return '호스트를 입력하세요.'
  const { port, connectTimeoutSeconds } = inputFromForm(values)
  if (!Number.isInteger(port) || port < 1 || port > 65535) return '포트는 1~65535 사이의 정수로 입력하세요.'
  if (!values.userFilter.trim()) return '사용자 검색 필터를 입력하세요.'
  if (!Number.isInteger(connectTimeoutSeconds) || connectTimeoutSeconds < 1 || connectTimeoutSeconds > 30) return '연결 제한 시간은 1~30초 사이의 정수로 입력하세요.'
  return null
}
