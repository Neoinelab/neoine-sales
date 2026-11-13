import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { openEdit } from './testHelpers'

const tile = (name: string) => screen.getByRole('region', { name })
const fieldOf = (scope: HTMLElement, label: string) => within(scope).getByLabelText(label).closest('.field')

/**
 * `*`는 form.css의 두 선택자가 그린다(jsdom은 ::after를 계산하지 않아 구조로 확인).
 * `.deal-form .field.required > label::after`: 칸의 직접 자식에 label이 있다.
 * `.deal-form .field.required > span:first-child::after`: 칸의 첫 자식이 span이다(루트가 label인 칸).
 * required 클래스만 있고 둘 다 아니면 `*`가 안 보인다.
 */
const drawsMark = (field: Element | null) =>
  field !== null &&
  field.matches('.deal-form .field.required') &&
  (Array.from(field.children).some((c) => c.tagName === 'LABEL') || field.firstElementChild?.tagName === 'SPAN')

async function openNew() {
  const view = await renderAt('/deals/new')
  await screen.findByRole('heading', { name: 'Deal 등록' })
  await screen.findByLabelText('Deal Name')
  return view
}

/** 고객 회사명·담당자명은 필수 표시, 고객 나머지 칸과 파트너 다섯 칸은 필수 표시 없음. Deal Name·Solution은 기준(필수 표시 있음). */
function expectCustomerMarks() {
  const info = tile('Deal 정보')
  expect(drawsMark(fieldOf(info, 'Deal Name'))).toBe(true)
  expect(drawsMark(fieldOf(info, 'Solution'))).toBe(true)

  const customer = tile('고객')
  expect(drawsMark(fieldOf(customer, '고객 회사명'))).toBe(true)
  expect(drawsMark(fieldOf(customer, '고객 담당자명'))).toBe(true)
  for (const label of ['고객 직급', '고객 이메일', '고객 전화']) expect(fieldOf(customer, label)).not.toHaveClass('required')

  const partner = tile('파트너')
  for (const label of ['파트너 회사명', '파트너 담당자명', '파트너 직급', '파트너 이메일', '파트너 전화']) {
    expect(fieldOf(partner, label)).not.toHaveClass('required')
  }
}

describe('Deal 폼 필수 표시', () => {
  // 등록 폼의 고객 회사명·담당자명은 다른 필수 칸과 같은 필수 표시이고 다른 고객 칸과 파트너 칸에는 없다
  // 테스트 코드: DE-113
  it('marks the customer company and name as required on the registration form', async () => {
    // when: 등록 폼을 연다
    await openNew()

    // then: 고객 회사명·담당자명이 Deal Name·Solution과 같은 필수 표시이고 접근 이름은 그대로이며, 직급·이메일·전화와 파트너 칸에는 없다
    expectCustomerMarks()
  })

  // 수정 폼에서도 같다
  // 테스트 코드: DE-113
  it('marks the customer company and name as required on the edit form of a deal that has a partner', async () => {
    // when: 파트너가 있는 Deal의 수정 폼을 연다
    await openEdit('누리통신 MFA')

    // then: 등록 폼과 같은 표시이고 파트너 칸에는 필수 표시가 없다
    expect(within(tile('파트너')).getByLabelText('파트너 회사명')).toHaveValue('에이원시스템')
    expectCustomerMarks()
  })

  // Owner 칸은 필수 표시이고 늘 값이 있는 Status·Forecast에는 없다
  // 테스트 코드: DE-114
  it('marks Owner as required but not Status and Forecast', async () => {
    // when: 등록 폼을 연다
    await openNew()
    const info = tile('Deal 정보')

    // then: Owner는 `*`를 그리는 필수 표시 구조이고 Status·Forecast는 아니다
    expect(drawsMark(fieldOf(info, 'Owner'))).toBe(true)
    expect(fieldOf(info, 'Status')).not.toHaveClass('required')
    expect(fieldOf(info, 'Forecast')).not.toHaveClass('required')
  })
})
