import { describe, expect, it } from 'vitest'
import type { DirectorySettingsInput } from '../../../shared/model/types'
import { toDirectoryRequest } from './settings'

const INPUT: DirectorySettingsInput = {
  serverUrls: ['ldaps://dc'],
  useStarttls: false,
  caCertPem: '-----BEGIN CERTIFICATE-----',
  bindTemplate: 'CORP\\{login_id}',
  baseDn: 'dc=a',
  userFilter: '(x)',
  displayNameAttribute: 'displayName',
  emailAttribute: 'mail',
  connectTimeoutSeconds: 7,
  receiveTimeoutSeconds: 11,
}

describe('toDirectoryRequest', () => {
  it('converts every field to the snake_case request', () => {
    expect(toDirectoryRequest(INPUT)).toEqual({
      server_urls: ['ldaps://dc'],
      use_starttls: false,
      ca_cert_pem: '-----BEGIN CERTIFICATE-----',
      bind_template: 'CORP\\{login_id}',
      base_dn: 'dc=a',
      user_filter: '(x)',
      display_name_attribute: 'displayName',
      email_attribute: 'mail',
      connect_timeout_seconds: 7,
      receive_timeout_seconds: 11,
    })
  })
})
