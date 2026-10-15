import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../test/mockApp'
import { dealCodeOf, detailPath } from './detail/detailTestUtils'
import { DETAIL_URL, openEdit, pickPerson, save } from './form/testHelpers'

/** 화면 사이에 넘기는 저장 알림(location.state.notice)이 도착 화면에 보이고 한 번만 나오는지 본다. */

describe('삭제 후 목록 알림', () => {
  it('shows the deletion notice on the list and drops it after leaving the list', async () => {
    const code = await dealCodeOf(11)
    const view = await renderAt(await detailPath(11))
    await screen.findByRole('heading', { level: 1, name: '청명대학교 SSO/MFA' })
    await view.user.click(screen.getByRole('button', { name: 'Deal 삭제' }))
    const dialog = await screen.findByRole('dialog', { name: 'Deal 삭제' })
    await view.user.type(within(dialog).getByLabelText('Deal code 확인'), code)
    await view.user.click(within(dialog).getByRole('button', { name: '삭제' }))

    expect(await screen.findByText(`Deal ${code}이(가) 삭제되었습니다.`)).toBeVisible()

    // 다른 화면으로 갔다가 목록으로 돌아오면 다시 나오지 않는다.
    await view.user.click(screen.getByRole('link', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: 'Forecast' })
    await view.user.click(screen.getByRole('link', { name: 'Deals' }))
    await screen.findByRole('heading', { name: 'Deals' })
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    expect(screen.queryByText(`Deal ${code}이(가) 삭제되었습니다.`)).not.toBeInTheDocument()
  })

  it('can be closed with the close button', async () => {
    const code = await dealCodeOf(11)
    const view = await renderAt(await detailPath(11))
    await screen.findByRole('heading', { level: 1, name: '청명대학교 SSO/MFA' })
    await view.user.click(screen.getByRole('button', { name: 'Deal 삭제' }))
    const dialog = await screen.findByRole('dialog', { name: 'Deal 삭제' })
    await view.user.type(within(dialog).getByLabelText('Deal code 확인'), code)
    await view.user.click(within(dialog).getByRole('button', { name: '삭제' }))
    const notice = await screen.findByText(`Deal ${code}이(가) 삭제되었습니다.`)

    await view.user.click(within(notice.closest('[role="status"]') as HTMLElement).getByRole('button', { name: '닫기' }))

    expect(screen.queryByText(`Deal ${code}이(가) 삭제되었습니다.`)).not.toBeInTheDocument()
  })

  it('shows no notice when the list is opened directly', async () => {
    await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    expect(screen.queryByText(/삭제되었습니다/)).not.toBeInTheDocument()
  })
})

describe('저장 후 상세 알림', () => {
  it('shows the registration notice with the new code on the detail page', async () => {
    const { user, location } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('Deal Name'), '알림 확인 테스트')
    await pickPerson(user, '고객', '한빛은행', /정민수/)
    await user.type(screen.getByLabelText('매출금액'), '100000000')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    await save(user)
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))

    const code = location().replace('/deals/', '')
    expect(await screen.findByText(`Deal ${code}이(가) 등록되었습니다.`)).toBeVisible()
  })

  it('shows the saved notice after an edit and drops it after leaving the page', async () => {
    const { user, location, code } = await openEdit('대한제조 NGFW')
    await save(user)
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    expect(await screen.findByText('저장되었습니다.')).toBeVisible()

    await user.click(screen.getByRole('link', { name: '← 목록' }))
    await screen.findByRole('heading', { name: 'Deals' })
    await user.click(await screen.findByRole('link', { name: '대한제조 NGFW' }))
    await screen.findByRole('heading', { level: 1, name: '대한제조 NGFW' })
    expect(screen.queryByText('저장되었습니다.')).not.toBeInTheDocument()
  })

  it('shows the inline save notice on the detail page after the form save notice, and again on a second inline save', async () => {
    const { user, location, code } = await openEdit('대한제조 NGFW')
    await save(user)
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    await screen.findByText('저장되었습니다.')

    // 상세에는 수정 링크가 없다. 이어서 값을 클릭해 그 자리에서 고치고, 같은 알림이 다시 저장될 때마다 나오는지 본다.
    expect(screen.queryByRole('link', { name: '수정' })).not.toBeInTheDocument()
    for (const name of ['대한제조 NGFW 확장', '대한제조 NGFW 확장2']) {
      await user.click(await screen.findByTitle('Deal 이름 수정'))
      const input = screen.getByLabelText('Deal 이름')
      await user.clear(input)
      await user.type(input, `${name}{Enter}`)
      expect(await screen.findByText('Deal 이름이 변경되었습니다.')).toBeVisible()
      await user.click(within(screen.getByText('Deal 이름이 변경되었습니다.').closest('[role="status"]') as HTMLElement).getByRole('button', { name: '닫기' }))
      expect(screen.queryByText('Deal 이름이 변경되었습니다.')).not.toBeInTheDocument()
    }
  })

  it('shows no notice when the detail page is opened directly', async () => {
    await renderAt(await detailPath(11))
    await screen.findByRole('heading', { level: 1, name: '청명대학교 SSO/MFA' })
    expect(screen.queryByText('저장되었습니다.')).not.toBeInTheDocument()
  })
})
