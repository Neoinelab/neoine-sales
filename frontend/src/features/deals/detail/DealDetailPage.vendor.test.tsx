import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { detailPath } from '../../../test/detailTestUtils'
import { kvValue } from '../../../test/kvPairs'
import { renderAt } from '../../../test/mockApp'
import { seedVendorId } from '../../../test/fixtures/vendors'

afterEach(() => vi.restoreAllMocks())

const infoTile = () => screen.getByRole('region', { name: 'Deal 정보' })
const optionNames = (select: HTMLElement) => within(select).getAllByRole('option').map((o) => o.textContent)

/** 시드 Deal 1(한빛은행 ITDR 도입, Silverfort / ITDR)의 상세를 연다. */
async function openDeal1() {
  const path = await detailPath(1)
  const view = await renderAt(path)
  await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
  return { ...view, code: path.replace('/deals/', '') }
}

describe('Vendor·Solution 인라인 편집', () => {
  // Vendor 선택에는 등록 Vendor만 있고('선택 안 함' 없음) 현재 값이 골라져 있다.
  // 테스트 코드: DD-080
  it('offers every registered vendor without a none option and the current one is selected', async () => {
    // given: Vendor가 Silverfort인 Deal
    const { user } = await openDeal1()


    // when: Vendor 편집을 연다
    await user.click(screen.getByRole('button', { name: 'Vendor 수정' }))
    const select = screen.getByRole('combobox', { name: 'Vendor' })
    await within(select).findByRole('option', { name: 'Okta' })

    // then: 옵션이 등록 Vendor 목록뿐이고 Silverfort가 선택돼 있다
    expect(optionNames(select)).toEqual([
      'CrowdStrike', 'CyberArk', 'Okta', 'Palo Alto', 'SentinelOne', 'Silverfort', 'Splunk', 'Tenable', 'Veeam', 'Zscaler',
    ])
    expect(select).toHaveDisplayValue('Silverfort')
  })

  // Solution을 텍스트로 고치면 solution만 보낸다.
  // 테스트 코드: DD-080
  it('edits the solution as text and sends only solution', async () => {
    // given: Solution이 ITDR인 Deal
    const { user, code } = await openDeal1()
    const update = vi.spyOn(gateway.deals, 'update')

    await user.click(screen.getByRole('button', { name: 'Solution 수정' }))
    const input = screen.getByLabelText('Solution')
    expect(input).toHaveValue('ITDR')

    // when: 공백이 낀 새 Solution을 입력하고 Enter를 누른다
    await user.clear(input)
    await user.type(input, '  Identity Threat {Enter}')

    // then: 알림이 보이고 solution만 담은 요청이 가며 공백이 지워진 값이 저장된다
    expect(await screen.findByText('Solution이 변경되었습니다.')).toBeVisible()
    expect(update).toHaveBeenCalledWith(code, { solution: 'Identity Threat' })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Solution 수정' })).toHaveTextContent('Identity Threat'))
    expect((await gateway.deals.get(code)).solution).toBe('Identity Threat')
  })

  // Solution이 그대로면 요청이 없다.
  // 테스트 코드: DD-080
  it('does not send a request when the solution text is unchanged', async () => {
    // given: Solution이 ITDR인 Deal
    const { user } = await openDeal1()
    const update = vi.spyOn(gateway.deals, 'update')

    // when: 공백만 덧붙이고 포커스를 옮긴다
    await user.click(screen.getByRole('button', { name: 'Solution 수정' }))
    await user.type(screen.getByLabelText('Solution'), '  ')
    await user.tab()

    // then: 수정 요청이 없다
    expect(update).not.toHaveBeenCalled()
  })

  // Solution을 비우면 문구 없이 solution ''만 보내 저장하고 값은 '—'로 보인다.
  // 테스트 코드: DD-080
  it('saves an emptied Solution as an empty string and shows a dash', async () => {
    // given: Solution이 ITDR인 Deal
    const { user, code } = await openDeal1()
    const update = vi.spyOn(gateway.deals, 'update')
    await user.click(screen.getByRole('button', { name: 'Solution 수정' }))
    const input = screen.getByLabelText('Solution')

    // when: Solution을 지우고 Enter를 누른다
    await user.clear(input)
    await user.type(input, '{Enter}')

    // then: 알림이 보이고 solution ''만 담은 요청이 가며 값이 '—'로 보인다
    expect(await screen.findByText('Solution이 변경되었습니다.')).toBeVisible()
    expect(update).toHaveBeenCalledWith(code, { solution: '' })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Solution 수정' })).toHaveTextContent('—'))
    expect((await gateway.deals.get(code)).solution).toBe('')
  })

  // Vendor를 바꾸면 vendor만 보내고 Solution은 유지된다.
  // 테스트 코드: DD-080
  it('vendor change sends only vendor and keeps the solution', async () => {
    // given: Vendor Silverfort, Solution ITDR인 Deal
    const { user, code } = await openDeal1()
    const update = vi.spyOn(gateway.deals, 'update')

    await user.click(screen.getByRole('button', { name: 'Vendor 수정' }))
    const select = screen.getByRole('combobox', { name: 'Vendor' })
    await within(select).findByRole('option', { name: 'Okta' })

    // when: Vendor를 Okta로 고른다
    await user.selectOptions(select, 'Okta')

    // then: vendorId만 담은 요청이 가고 Vendor는 Okta, Solution은 ITDR이다
    expect(await screen.findByText('Vendor가 변경되었습니다.')).toBeVisible()
    expect(screen.queryByText(/Solution은 비워졌습니다/)).not.toBeInTheDocument()
    expect(update).toHaveBeenCalledWith(code, { vendorId: seedVendorId('Okta') })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Vendor 수정' })).toHaveTextContent('Okta'))
    expect(screen.getByRole('button', { name: 'Solution 수정' })).toHaveTextContent('ITDR')
    const saved = await gateway.deals.get(code)
    expect(saved.vendor?.name).toBe('Okta')
    expect(saved.solution).toBe('ITDR')
  })

  // 같은 Vendor를 다시 고르면 요청이 없다.
  // 테스트 코드: DD-080
  it('does nothing when the same vendor is chosen again', async () => {
    // given: Vendor가 Silverfort인 Deal
    const { user } = await openDeal1()
    const update = vi.spyOn(gateway.deals, 'update')

    await user.click(screen.getByRole('button', { name: 'Vendor 수정' }))
    const select = screen.getByRole('combobox', { name: 'Vendor' })
    await within(select).findByRole('option', { name: 'Silverfort' })

    // when: 같은 Vendor를 고른다
    await user.selectOptions(select, 'Silverfort')
    await user.tab()

    // then: 수정 요청이 없다
    expect(update).not.toHaveBeenCalled()
  })

  // Solution이 빈 Deal은 Solution이 '—'로 보이고 Vendor는 그대로 보인다.
  // 테스트 코드: DD-080
  it('shows a deal with an empty Solution as a dash and keeps the Vendor name', async () => {
    // given: Solution이 빈 Deal
    const path = await detailPath(1)
    await renderAt(path, { seed: 'legacy-solution' })
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })

    // when: Deal 상세를 본다
    // then: Solution은 '—', Vendor는 Silverfort다
    expect(screen.getByRole('button', { name: 'Solution 수정' })).toHaveTextContent('—')
    expect(screen.getByRole('button', { name: 'Vendor 수정' })).toHaveTextContent('Silverfort')
  })

  // Solution이 빈 Deal도 Vendor를 인라인으로 바꿀 수 있다.
  // 테스트 코드: DD-080
  it('changes the vendor inline on a deal whose solution is empty', async () => {
    // given: Solution이 빈 Deal
    const path = await detailPath(1)
    const { user } = await renderAt(path, { seed: 'legacy-solution' })
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
    const code = path.replace('/deals/', '')
    const update = vi.spyOn(gateway.deals, 'update')

    await user.click(screen.getByRole('button', { name: 'Vendor 수정' }))
    const select = screen.getByRole('combobox', { name: 'Vendor' })
    await within(select).findByRole('option', { name: 'Okta' })

    // when: Vendor를 Okta로 고른다
    await user.selectOptions(select, 'Okta')

    // then: 알림이 보이고 vendorId만 보내며 Solution은 빈 값 그대로다
    expect(await screen.findByText('Vendor가 변경되었습니다.')).toBeVisible()
    expect(update).toHaveBeenCalledWith(code, { vendorId: seedVendorId('Okta') })
    const stored = await gateway.deals.get(code)
    expect([stored.vendor?.name, stored.solution]).toEqual(['Okta', ''])
  })

  // user에게 Vendor·Solution은 편집 버튼 없는 글자다.
  // 테스트 코드: DD-073
  it('shows the names as plain text without edit buttons for a viewer', async () => {
    // given: user 역할 사용자
    await renderAt(await detailPath(1), { role: 'user' })

    // when: Deal 상세를 연다
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })

    // then: Vendor·Solution 값이 보이고 수정 버튼이 없다
    expect(kvValue(infoTile(), 'Vendor')).toHaveTextContent('Silverfort')
    expect(kvValue(infoTile(), 'Solution')).toHaveTextContent('ITDR')
    expect(screen.queryByRole('button', { name: 'Vendor 수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Solution 수정' })).not.toBeInTheDocument()
  })

  // Vendor를 바꾸면 Deal History에 Vendor 변경만 남는다.
  // 테스트 코드: DD-080
  it('records only the vendor change in the Deal History when the vendor changes', async () => {
    // given: Vendor Silverfort인 Deal
    const { user, code } = await openDeal1()

    await user.click(screen.getByRole('button', { name: 'Vendor 수정' }))
    const select = screen.getByRole('combobox', { name: 'Vendor' })
    await within(select).findByRole('option', { name: 'Okta' })
    await user.selectOptions(select, 'Okta')
    await screen.findByText('Vendor가 변경되었습니다.')

    const entries = await gateway.history.list(code, {})

    // when: Vendor를 Okta로 바꾼다
    const pairs = entries.filter((h) => h.target === 'Vendor' || h.target === 'Solution').map((h) => [h.target, h.before, h.after])

    // then: Vendor 이력 한 건(Silverfort에서 Okta)뿐이다
    expect(pairs).toEqual([['Vendor', 'Silverfort', 'Okta']])
  })

  // Solution을 바꾸면 Deal History에 텍스트 변경이 남는다.
  // 테스트 코드: DD-080
  it('records the solution text change in the Deal History', async () => {
    // given: Solution ITDR인 Deal
    const { user, code } = await openDeal1()

    await user.click(screen.getByRole('button', { name: 'Solution 수정' }))
    const input = screen.getByLabelText('Solution')
    await user.clear(input)
    await user.type(input, 'MFA{Enter}')
    await screen.findByText('Solution이 변경되었습니다.')

    // when: Solution을 MFA로 바꾼다
    const entries = await gateway.history.list(code, {})

    // then: Solution 이력 한 건(ITDR에서 MFA)이다
    expect(entries.filter((h) => h.target === 'Solution').map((h) => [h.before, h.after])).toEqual([['ITDR', 'MFA']])
  })
})
