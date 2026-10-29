import { describe, expect, it } from 'vitest'
import type { Schemas } from '../../../shared/api/client'
import { BIND_PASSWORD, DIRECTORY_INPUT } from '../../../test/directoryFixtures'
import { toDirectoryRequest, toDirectorySettings } from './settings'

describe('toDirectoryRequest', () => {
  it('converts the seven fields to the snake_case request', () => {
    expect(toDirectoryRequest(DIRECTORY_INPUT)).toEqual({
      host: 'dc1.corp.test',
      port: 636,
      security: 'ssl',
      bind_account: 'CORP\\svc-sales',
      bind_password: BIND_PASSWORD,
      user_filter: '(sAMAccountName={login_id})',
      connect_timeout_seconds: 5,
    })
  })

  it('leaves the bind_password key out when the stored password is kept', () => {
    const request = toDirectoryRequest({ ...DIRECTORY_INPUT, bindPassword: null })

    expect(request).not.toHaveProperty('bind_password')
    expect(Object.keys(request).sort()).toEqual(
      ['bind_account', 'connect_timeout_seconds', 'host', 'port', 'security', 'user_filter'].sort(),
    )
  })

  it('never sends the removed fields', () => {
    const request = toDirectoryRequest(DIRECTORY_INPUT)

    for (const removed of ['server_urls', 'use_starttls', 'ca_cert_pem', 'bind_template', 'base_dn', 'display_name_attribute', 'email_attribute', 'receive_timeout_seconds']) {
      expect(request).not.toHaveProperty(removed)
    }
  })

  it.each(['none', 'ssl', 'starttls'] as const)('passes the %s security mode through', (security) => {
    expect(toDirectoryRequest({ ...DIRECTORY_INPUT, security })).toMatchObject({ security })
  })
})

describe('toDirectorySettings', () => {
  const ROW = {
    host: 'dc1.corp.test',
    port: 389,
    security: 'starttls',
    bind_account: 'svc@corp.test',
    bind_credential_status: 'unreadable',
    user_filter: '(x={login_id})',
    connect_timeout_seconds: 9,
    base_dn: 'ou=staff,dc=corp,dc=test',
    revision: 2,
    updated_at: '2026-10-15T10:00:00+09:00',
    updated_by: null,
  } as unknown as Schemas['DirectorySettingsResponse']

  it('converts the response to camelCase and keeps the read-only Base DN', () => {
    expect(toDirectorySettings(ROW)).toEqual({
      host: 'dc1.corp.test',
      port: 389,
      security: 'starttls',
      bindAccount: 'svc@corp.test',
      bindCredentialStatus: 'unreadable',
      userFilter: '(x={login_id})',
      connectTimeoutSeconds: 9,
      baseDn: 'ou=staff,dc=corp,dc=test',
      revision: 2,
      updatedAt: '2026-10-15T10:00:00+09:00',
      updatedBy: null,
    })
  })
})
