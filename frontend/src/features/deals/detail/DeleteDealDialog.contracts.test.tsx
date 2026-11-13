import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { dealCodeOf, detailPath } from '../../../test/detailTestUtils'
import { defaultMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'
import { renderAt } from '../../../test/mockApp'

/** Deal 삭제 확인 팝업의 라이선스 계약 건수: 계약도 함께 삭제되므로 건수를 알려 준다. */
async function openDialog(no: number, title: string) {
  // 계약이 있는 Deal은 Won(완료)이라 admin만 지울 수 있다(DD-R41).
  const view = await renderAt(await detailPath(no), { role: 'admin' })
  await screen.findByRole('heading', { level: 1, name: title })
  await view.user.click(screen.getByRole('button', { name: 'Deal 삭제' }))
  return { ...view, dialog: await screen.findByRole('dialog', { name: 'Deal 삭제' }) }
}

describe('Deal 삭제 팝업의 계약 건수', () => {
  // Deal 삭제 확인에 함께 지워질 라이선스 계약 건수가 보인다.
  // 테스트 코드: LC-081
  it('shows the number of license contracts that are deleted together', async () => {
    // given: 계약 2건이 있는 Deal 상세
    const code = await dealCodeOf(11)
    // when: Deal 삭제를 누른다
    await defaultMock.signInAs(USER_ID.root)
    const count = (await gateway.deals.impact(code)).licenseContractCount
    // then: 확인 대화상자에 라이선스 계약 2건이 보인다
    expect(count).toBeGreaterThan(0)

    const { dialog } = await openDialog(11, '청명대학교 SSO/MFA')

    await waitFor(() => expect(dialog).toHaveTextContent(`라이선스 계약 ${count}건`))
    expect(dialog).toHaveTextContent('복구할 수 없습니다')
  })

  // 계약이 없는 Deal은 0건으로 보인다.
  // 테스트 코드: LC-081
  it('shows 0 for a deal without contracts', async () => {
    // when: Deal 삭제를 누른다 (전제: 계약이 없는 Deal 상세)
    const { dialog } = await openDialog(2, '대한제조 MFA 확대')

    // then: 라이선스 계약 0건이 보인다
    await waitFor(() => expect(dialog).toHaveTextContent('라이선스 계약 0건'))
  })

  // 확인 뒤 삭제하면 그 Deal의 계약이 계약 목록에서 사라진다.
  // 테스트 코드: LC-081
  it('removes the contracts together with the deal', async () => {
    // given: 계약이 있는 Deal 상세
    const code = await dealCodeOf(11)
    await defaultMock.signInAs(USER_ID.root)
    const before = (await gateway.licenseContracts.list({ sort: 'licenseEnd', order: 'asc' }, 0, 200)).items.filter((c) => c.dealCode === code)
    expect(before.length).toBeGreaterThan(0)

    // when: 삭제를 확인한다
    await gateway.deals.remove(code, code)

    // then: 그 Deal의 계약이 계약 목록에 없다
    const after = (await gateway.licenseContracts.list({ sort: 'licenseEnd', order: 'asc' }, 0, 200)).items.filter((c) => c.dealCode === code)
    expect(after).toEqual([])
  })
})
