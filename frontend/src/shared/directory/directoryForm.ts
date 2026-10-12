import type { Schemas } from '../api/client'

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

export type DirectoryRequest = Schemas['DirectorySettingsRequest']

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

export function formFromSettings(s: Schemas['DirectorySettingsResponse']): DirectoryFormValues {
  return {
    serverUrls: s.server_urls.join('\n'),
    useStarttls: s.use_starttls,
    caCertPem: s.ca_cert_pem ?? '',
    bindTemplate: s.bind_template,
    baseDn: s.base_dn,
    userFilter: s.user_filter,
    displayNameAttribute: s.display_name_attribute,
    emailAttribute: s.email_attribute,
    connectTimeoutSeconds: String(s.connect_timeout_seconds),
    receiveTimeoutSeconds: String(s.receive_timeout_seconds),
  }
}

/** 서버 URL은 줄 단위로 자르고 빈 줄을 버린다. 비어 있는 CA 인증서는 null로 보낸다. */
export function requestFromForm(v: DirectoryFormValues): DirectoryRequest {
  return {
    server_urls: v.serverUrls
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line !== ''),
    use_starttls: v.useStarttls,
    ca_cert_pem: v.caCertPem.trim() === '' ? null : v.caCertPem,
    bind_template: v.bindTemplate,
    base_dn: v.baseDn,
    user_filter: v.userFilter,
    display_name_attribute: v.displayNameAttribute,
    email_attribute: v.emailAttribute,
    connect_timeout_seconds: Number(v.connectTimeoutSeconds),
    receive_timeout_seconds: Number(v.receiveTimeoutSeconds),
  }
}
