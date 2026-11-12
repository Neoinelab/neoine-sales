import { describe, expect, it } from 'vitest'
import { ApiError, call, errorFields, errorMessage } from './problem'

const res = (status: number) => new Response(null, { status })

describe('call', () => {
  // 성공 응답이면 data를 돌려준다.
  it('returns the data of a successful response', async () => {
    // given: data가 있는 200 응답
    const response = Promise.resolve({ data: { id: '1' }, response: res(200) })

    // when: 화면이 응답을 푼다
    const data = await call(response)

    // then: data가 그대로 돌아온다
    expect(data).toEqual({ id: '1' })
  })

  // 실패 응답이면 Problem 문서를 담은 ApiError를 던진다.
  it('throws an ApiError carrying the problem document', async () => {
    // given: 409 invalid-state Problem 응답
    const error = {
      type: 'https://x/problems/invalid-state',
      title: 't',
      status: 409,
      detail: '이 고객을 참조하는 Deal이 있어 삭제할 수 없습니다',
    }

    // when: 화면이 응답을 푼다
    const failure = call(Promise.resolve({ error, response: res(409) }))

    // then: 상태 409, kind invalid-state이고 서버 문구가 담겨 있다
    await expect(failure).rejects.toMatchObject({ status: 409, kind: 'invalid-state' })
    await expect(failure).rejects.toThrow('참조하는 Deal')
  })

  // 422 request-validation은 서버 문구 뒤에 칸 오류를 body 접두어 없이 붙인다.
  // 테스트 코드: PL-067
  it('lists field errors of a request validation problem without the body prefix', () => {
    // when: loc가 있는 오류 항목을 가진 422 ApiError를 만든다 (문구는 생성 시 계산)
    const error = new ApiError(422, {
      type: 'https://x/problems/request-validation',
      title: 't',
      status: 422,
      detail: '요청 형식이 올바르지 않습니다',
      errors: [{ loc: ['body', 'company_name'], msg: 'Field required' }],
    })

    // then: 서버 문구에 loc 첫 조각을 뺀 경로와 msg가 붙는다
    expect(error.message).toBe('요청 형식이 올바르지 않습니다 — company_name: Field required')
  })

  // Problem이 아닌 본문의 실패는 상태가 든 고정 문구를 보인다.
  // 테스트 코드: PL-068
  it('falls back to a generic message when the body is not a problem document', async () => {
    // when: 화면이 오류를 문구로 바꾼다 (전제: Problem이 아닌 본문의 502 응답)
    const failure = call(Promise.resolve({ error: 'oops', response: res(502) }))

    // then: "요청에 실패했습니다 (502)"다
    await expect(failure).rejects.toThrow('요청에 실패했습니다 (502)')
  })
})

describe('errorMessage', () => {
  // ApiError가 아닌 오류는 원문 대신 고정 문구로 바꾼다.
  // 테스트 코드: PL-069
  it('hides unexpected error details', () => {
    // given: ApiError가 아닌 예외
    const failure = new TypeError('Failed to fetch')
    // when: 화면이 문구로 바꾼다
    const message = errorMessage(failure)
    // then: 네트워크 고정 문구이고 원문은 보이지 않는다
    expect(message).toBe('네트워크 오류가 발생했습니다. 잠시 후 다시 시도하세요.')
    expect(message).not.toContain('Failed to fetch')
  })
})

describe('permission and verification problems (UI-10)', () => {
  // 403 forbidden Problem은 서버 detail을 그대로 보인다.
  // 테스트 코드: PL-067
  it('shows the server detail of a 403 forbidden problem', () => {
    // given: 403 forbidden Problem
    const error = new ApiError(403, {
      type: 'https://x/problems/forbidden',
      title: 'forbidden',
      status: 403,
      detail: '이 작업을 수행할 권한이 없습니다',
    })

    // when: 화면이 문구로 바꾼다
    const actual1 = errorMessage(error)
    const actual2 = errorMessage(error)

    // then: 서버 detail 그대로이고 kind 이름은 보이지 않는다
    expect(actual1).toBe('이 작업을 수행할 권한이 없습니다')
    expect(actual2).not.toMatch(/forbidden/i)
  })

  // Problem이 아닌 403은 상태 코드 대신 권한 안내 문구를 보인다.
  // 테스트 코드: PL-068
  it('explains a 403 without a problem document as missing permission instead of a status code', () => {
    // when: 화면이 문구로 바꾼다 (전제: Problem 없는 403)
    const message = errorMessage(new ApiError(403))
    // then: 권한 안내 문구이고 상태 코드는 없다
    expect(message).toBe('이 작업을 수행할 권한이 없습니다. 관리자에게 문의하세요.')

    expect(message).toContain('권한')
    expect(message).not.toContain('403')
  })

  // directory-verification-failed Problem은 실패한 단계(stage)를 노출한다.
  it('exposes the failed stage of a directory verification problem', () => {
    // when: stage가 있는 directory-verification-failed Problem으로 ApiError를 만든다
    const error = new ApiError(422, {
      type: 'https://x/problems/directory-verification-failed',
      title: 't',
      status: 422,
      detail: '확인 실패',
      stage: 'bind',
    } as never)

    // then: kind와 stage가 유지된다
    expect(error.kind).toBe('directory-verification-failed')
    expect((error as ApiError & { stage?: string }).stage).toBe('bind')
  })

  // 다른 Problem에는 stage가 없다.
  it('has no stage for other problems', () => {
    // when: stage 없는 invalid-state Problem으로 ApiError를 만든다
    const error = new ApiError(409, { type: 'https://x/problems/invalid-state', title: 't', status: 409, detail: 'x' })

    // then: stage가 없다
    expect((error as ApiError & { stage?: string }).stage).toBeUndefined()
  })
})

describe('problems with error items of another shape (Reports)', () => {
  // loc가 없는 오류 항목은 오류를 던지지 않고 건너뛴다.
  // 테스트 코드: PL-070
  it('ignores error items without loc instead of throwing', () => {
    // given: location/code/message 모양의 항목만 있는 invalid-report Problem
    const body = {
      type: 'https://x/problems/invalid-report',
      title: 't',
      status: 422,
      detail: '허용되지 않은 필드입니다: deal.nope',
      errors: [{ location: ['columns', 1, 'field'], code: 'unknown-field', message: '허용되지 않은 필드입니다: deal.nope' }],
    } as never

    // when: 문구를 만든다
    const create = () => new ApiError(422, body)
    // then: 오류 없이 서버 문구만 남는다
    expect(create).not.toThrow()
    expect(create().message).toBe('허용되지 않은 필드입니다: deal.nope')
  })

  // loc가 없는 항목과 있는 항목이 섞이면 loc가 있는 항목만 문구에 붙는다.
  // 테스트 코드: PL-070
  it('still lists the items that do have loc next to ones that do not', () => {
    // given: loc 없는 항목과 있는 항목이 섞인 Problem
    const body = {
      type: 'https://x/problems/request-validation',
      title: 't',
      status: 422,
      detail: '요청 형식이 올바르지 않습니다',
      errors: [{ code: 'x', message: 'y' }, { loc: ['body', 'row_limit'], msg: 'Field required' }],
    } as never

    // when: 문구를 만든다
    const message = new ApiError(422, body).message
    // then: loc가 있는 항목만 붙는다
    expect(message).toBe('요청 형식이 올바르지 않습니다 — row_limit: Field required')
  })

  // invalid-report Problem은 reportErrors를 그대로 담는다.
  it('carries the report issues of an invalid report problem', () => {
    // given: reportErrors가 있는 invalid-report Problem
    const reportErrors = [{ location: ['row_limit'], code: 'row-limit-invalid', message: '최대 행 수가 올바르지 않습니다' }]

    // when: ApiError를 만든다
    const error = new ApiError(422, {
      type: 'https://x/problems/invalid-report',
      title: 't',
      status: 422,
      detail: '최대 행 수가 올바르지 않습니다',
      reportErrors,
    })

    // then: kind가 invalid-report이고 reportErrors가 같다
    expect(error.kind).toBe('invalid-report')
    expect(error.problem?.reportErrors).toEqual(reportErrors)
  })
})

describe('errorFields', () => {
  // errorFields는 errors[].location의 첫 문자열 조각만 모은다.
  // 테스트 코드: PL-070
  it('collects the first string part of each location and skips items of another shape', () => {
    // given: location 항목과 loc 항목이 섞인 invalid-value Problem
    const error = new ApiError(422, {
      type: 'https://x/problems/invalid-value',
      title: 't',
      status: 422,
      detail: '값이 올바르지 않습니다',
      errors: [
        { location: ['password', 0], message: '짧습니다' },
        { location: [3], message: '숫자 위치' },
        { loc: ['body', 'name'], msg: 'Field required' },
      ],
    } as never)
    // when: 칸 이름을 모은다
    const fields = errorFields(error)
    // then: location의 첫 문자열 조각만 남는다
    expect(fields).toEqual(['password'])
    expect(errorFields(new TypeError('x'))).toEqual([])
  })
})
