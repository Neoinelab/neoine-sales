import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { listMemoryKey } from '../../shared/model/dealListMemory'
import { USER_ID } from '../../test/fake/seed/ids'
import { renderAt } from '../../test/mockApp'
import { ALL_DEALS } from './list/testHelpers'
import { dealCodeOf, detailPath } from '../../test/detailTestUtils'
import { DETAIL_URL, openEdit, pickPerson, save } from './form/testHelpers'

/** 화면 사이에 넘기는 저장 알림(location.state.notice)이 도착 화면에 보이고 한 번만 나오는지 본다. */

describe('삭제 후 목록 알림', () => {
  // Deal을 삭제하면 목록에 삭제 알림이 보이고, 목록을 떠났다 돌아오면 사라진다.
  it('shows the deletion notice on the list and drops it after leaving the list', async () => {
    // given: sales 사용자가 연도 전체 목록을 기억한 채 Deal 상세를 열었다
    // 기억한 목록 조건이 없으면 기본 조건(올해)이 붙으므로, 전체 Deal을 보도록 '연도 전체'를 기억해 둔다.
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), 'year=all')
    const code = await dealCodeOf(2)
    const view = await renderAt(await detailPath(2))
    await screen.findByRole('heading', { level: 1, name: '대한제조 MFA 확대' })
    await view.user.click(screen.getByRole('button', { name: 'Deal 삭제' }))
    const dialog = await screen.findByRole('dialog', { name: 'Deal 삭제' })
    await view.user.type(within(dialog).getByLabelText('Deal code 확인'), code)
    // when: 삭제 확인 창에서 code를 입력하고 삭제한다
    await view.user.click(within(dialog).getByRole('button', { name: '삭제' }))

    // then: 목록에 'Deal <code>이(가) 삭제되었습니다.'가 보이고, 다른 화면을 다녀오면 다시 나오지 않는다
    expect(await screen.findByText(`Deal ${code}이(가) 삭제되었습니다.`)).toBeVisible()

    // 다른 화면으로 갔다가 목록으로 돌아오면 다시 나오지 않는다.
    await view.user.click(screen.getByRole('link', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: 'Forecast' })
    await view.user.click(screen.getByRole('link', { name: 'Deals' }))
    await screen.findByRole('heading', { name: 'Deals' })
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    expect(screen.queryByText(`Deal ${code}이(가) 삭제되었습니다.`)).not.toBeInTheDocument()
  })

  // 삭제 알림은 닫기 버튼으로 닫을 수 있다.
  it('can be closed with the close button', async () => {
    // given: Deal을 삭제해 목록에 삭제 알림이 보인다
    const code = await dealCodeOf(2)
    const view = await renderAt(await detailPath(2))
    await screen.findByRole('heading', { level: 1, name: '대한제조 MFA 확대' })
    await view.user.click(screen.getByRole('button', { name: 'Deal 삭제' }))
    const dialog = await screen.findByRole('dialog', { name: 'Deal 삭제' })
    await view.user.type(within(dialog).getByLabelText('Deal code 확인'), code)
    await view.user.click(within(dialog).getByRole('button', { name: '삭제' }))
    const notice = await screen.findByText(`Deal ${code}이(가) 삭제되었습니다.`)

    // when: 알림의 닫기 버튼을 누른다
    await view.user.click(within(notice.closest('[role="status"]') as HTMLElement).getByRole('button', { name: '닫기' }))

    // then: 알림이 사라진다
    expect(screen.queryByText(`Deal ${code}이(가) 삭제되었습니다.`)).not.toBeInTheDocument()
  })

  // 목록을 직접 열면 알림이 없다.
  it('shows no notice when the list is opened directly', async () => {
    // when: 목록을 직접 연다
    await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    // then: 삭제 알림이 보이지 않는다
    expect(screen.queryByText(/삭제되었습니다/)).not.toBeInTheDocument()
  })
})

describe('저장 후 상세 알림', () => {
  // 등록하면 상세로 가며 새 code가 든 등록 알림을 보인다.
  // 테스트 코드: DE-108
  it('shows the registration notice with the new code on the detail page', async () => {
    // given: Deal 등록 화면이다.
    const { user, location } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    // when: 필수 값을 입력하고 저장한다.
    await user.type(screen.getByLabelText('Deal Name'), '알림 확인 테스트')
    await pickPerson(user, '고객', '한빛은행', /정민수/)
    await user.type(screen.getByLabelText('금액(단위:원)'), '100000000')
    await user.type(screen.getByLabelText('Solution'), 'ITDR')
    await user.type(screen.getByLabelText('Users count'), '10')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    await save(user)
    // then: 상세로 이동하고 'Deal <code>이(가) 등록되었습니다.'가 보인다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))

    const code = location().replace('/deals/', '')
    expect(await screen.findByText(`Deal ${code}이(가) 등록되었습니다.`)).toBeVisible()
  })

  // 수정하면 상세로 가며 '저장되었습니다.' 알림을 보이고 화면을 떠나면 사라진다.
  // 테스트 코드: DE-100
  it('shows the saved notice after an edit and drops it after leaving the page', async () => {
    // given: 수정 화면이다.
    const { user, location, code } = await openEdit('대한제조 NGFW')
    // when: 저장한다.
    await save(user)
    // then: 상세에 '저장되었습니다.'가 보인다.
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    expect(await screen.findByText('저장되었습니다.')).toBeVisible()

    // when: 목록에 다녀와 다시 상세를 연다.
    await user.click(screen.getByRole('link', { name: '← 목록' }))
    await screen.findByRole('heading', { name: 'Deals' })
    await user.click(await screen.findByRole('link', { name: '대한제조 NGFW' }))
    await screen.findByRole('heading', { level: 1, name: '대한제조 NGFW' })
    // then: 알림이 사라진다.
    expect(screen.queryByText('저장되었습니다.')).not.toBeInTheDocument()
  })

  // 폼 저장 알림 뒤에 상세에서 값을 고칠 때마다 인라인 저장 알림이 다시 나온다.
  it('shows the inline save notice on the detail page after the form save notice, and again on a second inline save', async () => {
    // given: 수정 화면에서 저장해 상세로 이동했고 '저장되었습니다.'가 보인다
    const { user, location, code } = await openEdit('대한제조 NGFW')
    await save(user)
    await waitFor(() => expect(location()).toBe(`/deals/${code}`))
    await screen.findByText('저장되었습니다.')

    // 상세에는 수정 링크가 없다. 이어서 값을 클릭해 그 자리에서 고치고, 같은 알림이 다시 저장될 때마다 나오는지 본다.
    expect(screen.queryByRole('link', { name: '수정' })).not.toBeInTheDocument()
    for (const name of ['대한제조 NGFW 확장', '대한제조 NGFW 확장2']) {
      // when: 상세에서 Deal 이름을 고쳐 Enter로 저장한다
      await user.click(await screen.findByTitle('Deal 이름 수정'))
      const input = screen.getByLabelText('Deal 이름')
      await user.clear(input)
      await user.type(input, `${name}{Enter}`)
      // then: 'Deal 이름이 변경되었습니다.'가 나온다
      expect(await screen.findByText('Deal 이름이 변경되었습니다.')).toBeVisible()

      // when: 알림을 닫는다
      await user.click(within(screen.getByText('Deal 이름이 변경되었습니다.').closest('[role="status"]') as HTMLElement).getByRole('button', { name: '닫기' }))
      // then: 알림이 사라진다
      expect(screen.queryByText('Deal 이름이 변경되었습니다.')).not.toBeInTheDocument()
    }
  })

  // 상세를 직접 열면 저장 알림이 없다.
  it('shows no notice when the detail page is opened directly', async () => {
    // when: Deal 상세를 직접 연다
    await renderAt(await detailPath(2))
    await screen.findByRole('heading', { level: 1, name: '대한제조 MFA 확대' })
    // then: '저장되었습니다.' 알림이 보이지 않는다
    expect(screen.queryByText('저장되었습니다.')).not.toBeInTheDocument()
  })
})
