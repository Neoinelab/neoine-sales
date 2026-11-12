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

describe('AD 검증 실패 단계 문구', () => {
  // 각 단계 안내는 확인할 곳을 알려 준다.
  // 테스트 코드: IN-079
  it.each([
    ['connect', '호스트·포트·방화벽'],
    ['tls', 'SSL/StartTLS'],
    ['service_bind', '바인드 계정'],
    ['base_dn', 'Base DN'],
    ['search', '사용자 필터'],
    ['bind', '관리자 비밀번호'],
  ])('explains the %s stage with what to check', (stage, hint) => {
    // when: 단계별 안내 문구를 읽는다
    const result = stageMessage(stage)
    // then: 단계마다 확인할 곳이 문구에 있다
    expect(result).toContain(hint)
  })

  // 여섯 단계의 화면 문구는 서로 다르다.
  // 테스트 코드: IN-079
  it('has a distinct message for each of the six stages', () => {
    // when: 여섯 단계의 안내 문구를 읽는다
    const messages = STAGES.map((stage) => stageMessage(stage))

    // then: 모두 다르다
    expect(messages.every((m) => typeof m === 'string' && m.length > 0)).toBe(true)
    expect(new Set(messages).size).toBe(STAGES.length)
  })

  // 화면 문구에 폐지된 CA 인증서·바인드 템플릿 언급이 없다.
  // 테스트 코드: IN-079
  it('no longer mentions the removed CA certificate or bind template', () => {
    // when: 여섯 단계 문구를 읽는다
    const messages = STAGES.map((stage) => stageMessage(stage))
    // then: CA 인증서·바인드 템플릿이 없다
    for (const message of messages) {
      expect(message).not.toMatch(/CA 인증서|바인드 템플릿|서버 URL/)
    }
  })

  // 모르는 단계나 없는 단계는 안내 문구가 없다.
  // 테스트 코드: IN-079
  it('returns undefined for an unknown or missing stage', () => {
    // when: 모르는 단계로 안내 문구를 읽는다
    const result1 = stageMessage('unknown')
    const result2 = stageMessage(undefined)
    const result3 = stageMessage(null)
    // then: undefined다
    expect(result1).toBeUndefined()
    expect(result2).toBeUndefined()
    expect(result3).toBeUndefined()
  })
})

describe('directoryErrorMessage', () => {
  // 확인 실패 오류는 단계별 안내 문구로 바뀐다.
  // 테스트 코드: IN-079
  it.each(STAGES)('shows the %s stage explanation for a failed verification', (stage) => {
    // when: 화면 문구로 바꾼다 (전제: 단계가 있는 directory-verification-failed 오류)
    const result = directoryErrorMessage(verificationFailed(stage))
    // then: 그 단계의 안내 문구다
    expect(result).toBe(stageMessage(stage))
  })

  // 모르는 단계는 서버 문구를 그대로 보인다.
  // 테스트 코드: IN-079
  it('falls back to the server message when the stage is unknown', () => {
    // when: 화면 문구로 바꾼다 (전제: 모르는 단계의 오류(detail X))
    const result1 = directoryErrorMessage(verificationFailed('weird', '서버가 준 문구'))
    const result2 = directoryErrorMessage(verificationFailed(undefined, '서버가 준 문구'))
    // then: 서버 문구 X다
    expect(result1).toBe('서버가 준 문구')
    expect(result2).toBe('서버가 준 문구')
  })

  // 429는 시도가 너무 많다는 문구다.
  // 테스트 코드: IN-079
  it('explains a too-many-attempts response', () => {
    // given: 429 오류
    const limited = new ApiError(429, {
      type: 'https://sales.neoine.test/problems/too-many-attempts',
      title: 'Too Many Attempts',
      status: 429,
      detail: '시도가 너무 많습니다.',
    })

    // when: 화면 문구로 바꾼다
    const result = directoryErrorMessage(limited)
    // then: '시도가 너무 많습니다. 잠시 후 다시 시도하세요.'다
    expect(result).toBe('시도가 너무 많습니다. 잠시 후 다시 시도하세요.')
  })

  // 그 밖의 오류(바인드 비밀번호 필요 등)는 서버 문구를 보인다.
  // 테스트 코드: IN-079
  it('shows the server message of other problems such as a missing bind password', () => {
    // given: 422 invalid-value 오류
    const invalid = new ApiError(422, {
      type: 'https://sales.neoine.test/problems/invalid-value',
      title: 'Invalid Value',
      status: 422,
      detail: 'bind_password: 서버나 바인드 계정을 바꾸면 비밀번호를 다시 입력해야 합니다',
    })

    // when: 화면 문구로 바꾼다
    const result = directoryErrorMessage(invalid)
    // then: 서버 문구 그대로다
    expect(result).toContain('비밀번호를 다시 입력해야 합니다')
  })
})
