/** mock 게이트웨이 테스트 도우미(운영 코드에서 쓰지 않는다). 고정 시계·지연 0ms로 새 인스턴스를 만든다. */

import type { ApiError } from '../../shared/api/problem'
import type { Gateway } from '../../gateway/types'
import type { DealInput } from '../../shared/model/types'
import { createMockGateway, type MockInstance, type MockOptions } from './index'
import { buildSampleSeed, seedDealCode } from '../fixtures/sampleSeed'
import { USER_ID } from './seed/ids'
import { seedVendorId } from '../fixtures/vendors'

export const TEST_NOW = '2026-10-15T09:00:00+09:00'
export const TEST_TODAY = '2026-10-15'

export type LoginKey = 'root' | 'kim' | 'park' | 'lee' | 'jung' | 'han'

export function newMock(options: MockOptions = {}): MockInstance {
  return createMockGateway({ now: TEST_NOW, latency: false, seed: buildSampleSeed, ...options })
}

/** 새 mock을 만들고 시드 사용자(`USER_ID[key]`)로 로그인한다. */
export async function mockAs(key: LoginKey | null, options: MockOptions = {}): Promise<MockInstance> {
  const mock = newMock(options)
  if (key !== null) await mock.gateway.auth.quickLogin(USER_ID[key])
  return mock
}

/** 계획 4.3의 Deal 번호(1~24) → Deal code. */
export function dealCode(no: number): string {
  return seedDealCode(no, TEST_TODAY)
}

/** reject되는 약속의 ApiError를 돌려준다. 성공하면 실패시킨다. */
export async function rejection(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (error) {
    return error as ApiError
  }
  throw new Error('reject되어야 하는데 성공했습니다.')
}

export async function expectApiError(
  promise: Promise<unknown>,
  status: number,
  message?: string | RegExp,
): Promise<ApiError> {
  const error = await rejection(promise)
  expect(error.status).toBe(status)
  if (typeof message === 'string') expect(error.message).toBe(message)
  else if (message) expect(error.message).toMatch(message)
  return error
}

/** 시드 연락처 id 조회(회사, 담당자 이름, 구분). 동명이인은 title로 구분. */
export async function contactIdOf(
  gw: Gateway,
  kind: 'customer' | 'partner',
  company: string,
  name: string,
  title?: string,
): Promise<number> {
  const rows = await gw.contacts.byCompany(kind, company)
  const found = rows.find((c) => c.name === name && (title === undefined || c.title === title))
  if (!found) throw new Error(`연락처 없음: ${company} ${name}`)
  return found.id
}

/** 가장 단순한 유효 Deal 입력(고객 한빛은행 정민수, 파트너 없음). */
export function dealInput(ownerId: number, over: Partial<DealInput> = {}): DealInput {
  return {
    name: '테스트 Deal',
    ownerId,
    vendorId: seedVendorId('Silverfort'),
    solution: 'ITDR',
    users: 100,
    statusKey: 'prospecting',
    forecastKey: 'pipeline',
    revenueAmount: 500_000_000,
    revenueDate: '2027-01-31',
    customer: { contactId: null, company: '한빛은행', name: '정민수', title: '과장', email: null, phone: null },
    partner: null,
    quote: { submitted: null, submittedDate: null },
    poc: { state: null, completedDate: null },
    procurement: '',
    bant: { budget: null, authority: null, need: null, timeline: null },
    ...over,
  }
}

/** 가짜 File(크기를 지정). 실제로 큰 버퍼를 만들지 않는다. */
export function fakeFile(name: string, size = 10, type = 'application/pdf'): File {
  const file = new File(['x'], name, { type })
  Object.defineProperty(file, 'size', { value: size })
  return file
}
