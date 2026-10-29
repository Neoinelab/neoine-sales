import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/problem'
import { directoryErrorMessage, stageMessage } from './messages'

const STAGES = ['connect', 'tls', 'service_bind', 'base_dn', 'search', 'bind'] as const

function verificationFailed(stage: string | undefined, detail = '서버 문구') {
  return new ApiError(422, {
    type: 'https://sales.neoine.test/problems/directory-verification-failed',
    title: 'Directory Verification Failed',
    status: 422,
    detail,
    ...(stage ? { stage } : {}),
  })
}

describe('AD 검증 실패 단계 문구 (AC6)', () => {
  it.each([
    ['connect', '호스트·포트·방화벽'],
    ['tls', 'SSL/StartTLS'],
    ['service_bind', '바인드 계정'],
    ['base_dn', 'Base DN'],
    ['search', '사용자 필터'],
    ['bind', '관리자 비밀번호'],
  ])('explains the %s stage with what to check', (stage, hint) => {
    expect(stageMessage(stage)).toContain(hint)
  })

  it('has a distinct message for each of the six stages', () => {
    const messages = STAGES.map((stage) => stageMessage(stage))

    expect(messages.every((m) => typeof m === 'string' && m.length > 0)).toBe(true)
    expect(new Set(messages).size).toBe(STAGES.length)
  })

  it('no longer mentions the removed CA certificate or bind template', () => {
    for (const stage of STAGES) {
      expect(stageMessage(stage)).not.toMatch(/CA 인증서|바인드 템플릿|서버 URL/)
    }
  })

  it('returns undefined for an unknown or missing stage', () => {
    expect(stageMessage('unknown')).toBeUndefined()
    expect(stageMessage(undefined)).toBeUndefined()
    expect(stageMessage(null)).toBeUndefined()
  })
})

describe('directoryErrorMessage', () => {
  it.each(STAGES)('shows the %s stage explanation for a failed verification', (stage) => {
    expect(directoryErrorMessage(verificationFailed(stage))).toBe(stageMessage(stage))
  })

  it('falls back to the server message when the stage is unknown', () => {
    expect(directoryErrorMessage(verificationFailed('weird', '서버가 준 문구'))).toBe('서버가 준 문구')
    expect(directoryErrorMessage(verificationFailed(undefined, '서버가 준 문구'))).toBe('서버가 준 문구')
  })

  it('explains a too-many-attempts response', () => {
    const limited = new ApiError(429, {
      type: 'https://sales.neoine.test/problems/too-many-attempts',
      title: 'Too Many Attempts',
      status: 429,
      detail: '시도가 너무 많습니다.',
    })

    expect(directoryErrorMessage(limited)).toBe('시도가 너무 많습니다. 잠시 후 다시 시도하세요.')
  })

  it('shows the server message of other problems such as a missing bind password', () => {
    const invalid = new ApiError(422, {
      type: 'https://sales.neoine.test/problems/invalid-value',
      title: 'Invalid Value',
      status: 422,
      detail: 'bind_password: 서버나 바인드 계정을 바꾸면 비밀번호를 다시 입력해야 합니다',
    })

    expect(directoryErrorMessage(invalid)).toContain('비밀번호를 다시 입력해야 합니다')
  })
})
