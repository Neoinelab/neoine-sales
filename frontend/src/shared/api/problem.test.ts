import { describe, expect, it } from 'vitest'
import { ApiError, call, errorMessage } from './problem'

const res = (status: number) => new Response(null, { status })

describe('call', () => {
  it('returns the data of a successful response', async () => {
    const data = await call(Promise.resolve({ data: { id: '1' }, response: res(200) }))

    expect(data).toEqual({ id: '1' })
  })

  it('throws an ApiError carrying the problem document', async () => {
    const error = {
      type: 'https://x/problems/invalid-state',
      title: 't',
      status: 409,
      detail: '이 고객을 참조하는 Deal이 있어 삭제할 수 없습니다',
    }

    const failure = call(Promise.resolve({ error, response: res(409) }))

    await expect(failure).rejects.toMatchObject({ status: 409, kind: 'invalid-state' })
    await expect(failure).rejects.toThrow('참조하는 Deal')
  })

  it('lists field errors of a request validation problem without the body prefix', () => {
    const error = new ApiError(422, {
      type: 'https://x/problems/request-validation',
      title: 't',
      status: 422,
      detail: '요청 형식이 올바르지 않습니다',
      errors: [{ loc: ['body', 'company_name'], msg: 'Field required' }],
    })

    expect(error.message).toBe('요청 형식이 올바르지 않습니다 — company_name: Field required')
  })

  it('falls back to a generic message when the body is not a problem document', async () => {
    const failure = call(Promise.resolve({ error: 'oops', response: res(502) }))

    await expect(failure).rejects.toThrow('요청에 실패했습니다 (502)')
  })
})

describe('errorMessage', () => {
  it('hides unexpected error details', () => {
    expect(errorMessage(new TypeError('Failed to fetch'))).toContain('네트워크 오류')
  })
})

describe('permission and verification problems (UI-10)', () => {
  it('shows the server detail of a 403 forbidden problem', () => {
    const error = new ApiError(403, {
      type: 'https://x/problems/forbidden',
      title: 'forbidden',
      status: 403,
      detail: '이 작업을 수행할 권한이 없습니다',
    })

    expect(errorMessage(error)).toBe('이 작업을 수행할 권한이 없습니다')
    expect(errorMessage(error)).not.toMatch(/forbidden/i)
  })

  it('explains a 403 without a problem document as missing permission instead of a status code', () => {
    const message = errorMessage(new ApiError(403))

    expect(message).toContain('권한')
    expect(message).not.toContain('403')
  })

  it('exposes the failed stage of a directory verification problem', () => {
    const error = new ApiError(422, {
      type: 'https://x/problems/directory-verification-failed',
      title: 't',
      status: 422,
      detail: '확인 실패',
      stage: 'bind',
    } as never)

    expect(error.kind).toBe('directory-verification-failed')
    expect((error as ApiError & { stage?: string }).stage).toBe('bind')
  })

  it('has no stage for other problems', () => {
    const error = new ApiError(409, { type: 'https://x/problems/invalid-state', title: 't', status: 409, detail: 'x' })

    expect((error as ApiError & { stage?: string }).stage).toBeUndefined()
  })
})

describe('problems with error items of another shape (Reports)', () => {
  it('ignores error items without loc instead of throwing', () => {
    const body = {
      type: 'https://x/problems/invalid-report',
      title: 't',
      status: 422,
      detail: '허용되지 않은 필드입니다: deal.nope',
      errors: [{ location: ['columns', 1, 'field'], code: 'unknown-field', message: '허용되지 않은 필드입니다: deal.nope' }],
    } as never

    const create = () => new ApiError(422, body)

    expect(create).not.toThrow()
    expect(create().message).toBe('허용되지 않은 필드입니다: deal.nope')
  })

  it('still lists the items that do have loc next to ones that do not', () => {
    const body = {
      type: 'https://x/problems/request-validation',
      title: 't',
      status: 422,
      detail: '요청 형식이 올바르지 않습니다',
      errors: [{ code: 'x', message: 'y' }, { loc: ['body', 'row_limit'], msg: 'Field required' }],
    } as never

    expect(new ApiError(422, body).message).toBe('요청 형식이 올바르지 않습니다 — row_limit: Field required')
  })

  it('carries the report issues of an invalid report problem', () => {
    const reportErrors = [{ location: ['row_limit'], code: 'row-limit-invalid', message: '최대 행 수가 올바르지 않습니다' }]
    const error = new ApiError(422, {
      type: 'https://x/problems/invalid-report',
      title: 't',
      status: 422,
      detail: '최대 행 수가 올바르지 않습니다',
      reportErrors,
    })

    expect(error.kind).toBe('invalid-report')
    expect(error.problem?.reportErrors).toEqual(reportErrors)
  })
})
