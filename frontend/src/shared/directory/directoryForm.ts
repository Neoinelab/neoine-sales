import type { DirectorySettings, DirectorySettingsInput } from '../model/types'

/** 폼 입력 상태. 서버 URL은 한 줄에 하나인 문자열, 숫자는 입력 중 상태를 위해 문자열로 둔다. */
export interface DirectoryFormValues {
  serverUrls: string
  useStarttls: boolean
  caCertPem: string
  bindTemplate: string
  baseDn: string
  userFilter: string
  displayNameAttribute: string
  emailAttribute: string
  connectTimeoutSeconds: string
  receiveTimeoutSeconds: string
}

export const DEFAULT_DIRECTORY_FORM: DirectoryFormValues = {
  serverUrls: '',
  useStarttls: false,
  caCertPem: '',
  bindTemplate: '',
  baseDn: '',
  userFilter: '(&(objectClass=user)(sAMAccountName={login_id}))',
  displayNameAttribute: 'displayName',
  emailAttribute: 'mail',
  connectTimeoutSeconds: '5',
  receiveTimeoutSeconds: '10',
}

/** 저장된 AD 설정 → 입력 칸 값(서버 URL은 한 줄에 하나, 숫자는 입력 중 상태를 위해 문자열). */
export function formFromDirectory(s: DirectorySettings): DirectoryFormValues {
  return {
    serverUrls: s.serverUrls.join('\n'),
    useStarttls: s.useStarttls,
    caCertPem: s.caCertPem ?? '',
    bindTemplate: s.bindTemplate,
    baseDn: s.baseDn,
    userFilter: s.userFilter,
    displayNameAttribute: s.displayNameAttribute,
    emailAttribute: s.emailAttribute,
    connectTimeoutSeconds: String(s.connectTimeoutSeconds),
    receiveTimeoutSeconds: String(s.receiveTimeoutSeconds),
  }
}

/** 입력 칸 값 → 게이트웨이 입력. 서버 URL은 줄 단위로 자르고 빈 줄을 버리며, 빈 CA 인증서는 null이다. */
export function inputFromForm(v: DirectoryFormValues): DirectorySettingsInput {
  return {
    serverUrls: v.serverUrls
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line !== ''),
    useStarttls: v.useStarttls,
    caCertPem: v.caCertPem.trim() === '' ? null : v.caCertPem,
    bindTemplate: v.bindTemplate,
    baseDn: v.baseDn,
    userFilter: v.userFilter,
    displayNameAttribute: v.displayNameAttribute,
    emailAttribute: v.emailAttribute,
    connectTimeoutSeconds: Number(v.connectTimeoutSeconds),
    receiveTimeoutSeconds: Number(v.receiveTimeoutSeconds),
  }
}
