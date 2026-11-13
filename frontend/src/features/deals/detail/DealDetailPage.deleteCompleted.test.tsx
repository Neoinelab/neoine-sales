import { screen, waitFor, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { listMemoryKey } from '../../../shared/model/dealListMemory'
import { dealCodeOf, detailPath } from '../../../test/detailTestUtils'
import { USER_ID } from '../../../test/fake/seed/ids'
import { renderAt } from '../../../test/mockApp'

/** 시드: 11 청명대학교 SSO/MFA = KIM의 Won(완료), 16 새론병원 SSO = KIM의 Lost, 20 세종에너지 ZTNA = KIM의 기회발굴/Pipeline. */
const COMPLETED_TITLE = '완료된 Deal은 관리자만 삭제할 수 있습니다.'

async function openDetail(no: number, title: string, role: 'sales' | 'admin' = 'sales') {
  const view = await renderAt(await detailPath(no), { role })
  await screen.findByRole('heading', { level: 1, name: title })
  return view
}

const deleteButton = () => screen.getByRole('button', { name: 'Deal 삭제' })

describe('완료된 Deal의 삭제 버튼 (DD-R41)', () => {
  // Owner 영업에게 완료된 자기 Deal의 삭제 버튼은 꺼져 있고 완료 문구가 보이며 편집은 된다
  // 테스트 코드: DD-122
  it('disables delete for the owner sales on a completed deal with the completed reason and keeps edit', async () => {
    // when: KIM이 자기 Won Deal의 상세를 연다
    await openDetail(11, '청명대학교 SSO/MFA')

    // then: Deal 삭제가 꺼져 있고 title이 완료 문구이며 이름 편집 버튼은 있다
    expect(deleteButton()).toBeDisabled()
    expect(deleteButton()).toHaveAttribute('title', COMPLETED_TITLE)
    expect(screen.getByTitle('Deal 이름 수정')).toBeVisible()
  })

  // 같은 영업의 Lost Deal은 지금처럼 삭제할 수 있다
  // 테스트 코드: DD-122
  it('keeps delete enabled for the owner sales on a lost deal', async () => {
    // when: KIM이 자기 Lost Deal의 상세를 연다
    await openDetail(16, '새론병원 SSO')

    // then: Deal 삭제가 켜져 있다
    expect(deleteButton()).toBeEnabled()
  })

  // admin은 완료된 Deal도 삭제 버튼이 켜져 있고 지울 수 있다
  // 테스트 코드: DD-123
  it('lets admin delete a completed deal owned by someone else and shows the notice on the list', async () => {
    // given: admin이 연도 전체 목록을 기억한 채 KIM의 Won Deal 상세를 연다
    window.sessionStorage.setItem(listMemoryKey(USER_ID.root), 'year=all')
    const code = await dealCodeOf(11)
    const { user, location } = await openDetail(11, '청명대학교 SSO/MFA', 'admin')
    expect(deleteButton()).toBeEnabled()

    // when: Deal 삭제를 눌러 정확한 code를 넣고 삭제한다
    await user.click(deleteButton())
    const dialog = await screen.findByRole('dialog', { name: 'Deal 삭제' })
    await user.type(within(dialog).getByLabelText('Deal code 확인'), code)
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))

    // then: 목록으로 가서 삭제 알림이 보인다
    await waitFor(() => expect(location()).toMatch(/^\/deals(\?|$)/))
    expect(await screen.findByText(`Deal ${code}이(가) 삭제되었습니다.`)).toBeVisible()
  })

  // Owner 영업이 상세에서 Won으로 확정하면 삭제 버튼이 바로 꺼진다
  // 테스트 코드: DD-126
  it('disables delete right after the owner sales confirms Won on the detail page', async () => {
    // given: KIM의 기회발굴/Pipeline Deal 상세 (삭제 버튼 켜짐)
    const { user } = await openDetail(20, '세종에너지 ZTNA')
    expect(deleteButton()).toBeEnabled()
    const bar = screen.getByRole('region', { name: 'Deal 정보' })

    // when: Status를 계약완료로 골라 매출 확정 대화상자에서 확정한다
    await pick(user, bar, 'Status', '계약완료')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    await user.click(within(dialog).getByRole('button', { name: '확정' }))

    // then: 저장 알림 뒤 Deal 삭제가 꺼지고 title이 완료 문구다
    expect(await screen.findByText(/함께 변경되었습니다/)).toBeVisible()
    await waitFor(() => expect(deleteButton()).toBeDisabled())
    expect(deleteButton()).toHaveAttribute('title', COMPLETED_TITLE)
  })
})

async function pick(user: UserEvent, bar: HTMLElement, field: 'Status' | 'Forecast', option: string) {
  await user.click(within(bar).getByRole('button', { name: `${field} 수정` }))
  await user.selectOptions(within(bar).getByLabelText(field), option)
}
