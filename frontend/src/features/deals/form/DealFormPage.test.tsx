import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { AMOUNT_INPUT_MESSAGE, AMOUNT_TOO_LARGE_MESSAGE } from '../../../shared/model/money'
import { renderAt } from '../../../test/mockApp'
import { DETAIL_URL, openList, pickPerson, save } from './testHelpers'
import { DEFAULT_DEALS_URL_PATTERN } from '../../../test/dealsUrl'

afterEach(() => vi.restoreAllMocks())

describe('Deal 등록 기본값 (T-FORM-02, T-FORM-03)', () => {
  it('starts with the signed-in sales user as owner, 기회발굴 and Pipeline', async () => {
    await renderAt('/deals/new')
    expect(await screen.findByRole('heading', { name: 'Deal 등록' })).toBeVisible()
    await waitFor(() => expect(screen.getByLabelText('Owner')).toHaveDisplayValue('김영업'))
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('기회발굴')
    expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Pipeline')
    expect(screen.getByText('KRW')).toBeVisible()
    expect(screen.getByLabelText('금액(단위:천원)')).toBeVisible()
  })

  it('offers only active sales users as owner candidates', async () => {
    await renderAt('/deals/new')
    const owner = await screen.findByLabelText('Owner')
    await within(owner).findByRole('option', { name: '박영업' })
    const names = within(owner)
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect(names).toEqual(['선택하세요', '김영업', '박영업', '이영업', '정영업'])
  })

  it('leaves the owner empty for an admin, who is not a sales user', async () => {
    await renderAt('/deals/new', { role: 'admin' })
    const owner = await screen.findByLabelText('Owner')
    await within(owner).findByRole('option', { name: '김영업' })
    expect(owner).toHaveDisplayValue('선택하세요')
  })

  it('lists all seven Status values and all six Forecast values', async () => {
    await renderAt('/deals/new')
    const status = await screen.findByLabelText('Status')
    await within(status).findByRole('option', { name: '계약완료' })
    expect(within(status).getAllByRole('option')).toHaveLength(7)
    expect(within(screen.getByLabelText('Forecast')).getAllByRole('option')).toHaveLength(6)
  })
})

describe('필수 입력과 오류 문구 (T-FORM-01, T-FORM-05)', () => {
  it('shows every required message at once and focuses the first invalid input', async () => {
    const { user } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await save(user)
    const alerts = (await screen.findAllByRole('alert')).map((a) => a.textContent)
    expect(alerts).toEqual(
      expect.arrayContaining([
        'Deal Name을 입력하세요.',
        '고객 회사명을 입력하세요.',
        '고객 담당자명을 입력하세요.',
        AMOUNT_INPUT_MESSAGE,
        'Expected Close를 입력하세요.',
      ]),
    )
    await waitFor(() => expect(screen.getByLabelText('Deal Name')).toHaveFocus())
  })

  it('rejects an amount over the maximum', async () => {
    const { user } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('금액(단위:천원)'), '9007199254741')
    await save(user)
    expect(await screen.findByText(AMOUNT_TOO_LARGE_MESSAGE)).toBeVisible()
  })

  it('asks for the owner when none is chosen and for a non-negative Users number', async () => {
    const { user } = await renderAt('/deals/new', { role: 'admin' })
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('Users'), '-1')
    await save(user)
    expect(await screen.findByText('Owner를 선택하세요.')).toBeVisible()
    expect(screen.getByText('Users는 0 이상의 정수로 입력하세요.')).toBeVisible()
  })

  it('asks for Users when it is left empty and does not call the gateway', async () => {
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('Deal Name'), 'Users 비움')
    await pickPerson(user, '고객', '한빛은행', /정민수/)
    await user.type(screen.getByLabelText('금액(단위:천원)'), '100000')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    await save(user)
    expect(await screen.findByText('Users를 입력하세요.')).toBeVisible()
    expect(create).not.toHaveBeenCalled()
    expect(location()).toBe('/deals/new')
  })

  it('saves Users of zero', async () => {
    const { user, location } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('Deal Name'), 'Users 영')
    await pickPerson(user, '고객', '한빛은행', /정민수/)
    await user.type(screen.getByLabelText('금액(단위:천원)'), '100000')
    await user.type(screen.getByLabelText('Solution'), 'ITDR')
    await user.type(screen.getByLabelText('Users'), '0')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    await save(user)
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const saved = await gateway.deals.get(location().replace('/deals/', ''))
    expect(saved.users).toBe(0)
  })

  it('requires both company and name once a partner is started', async () => {
    const { user } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('파트너 회사명'), '코어테크')
    await save(user)
    expect(await screen.findByText('파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.')).toBeVisible()
  })

  it('does not ask anything about the partner when it is left empty', async () => {
    const { user } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await save(user)
    await screen.findAllByRole('alert')
    expect(screen.queryByText(/파트너를 입력하면/)).not.toBeInTheDocument()
  })

  it('removes spaces typed into the customer company and explains why', async () => {
    const { user } = await renderAt('/deals/new')
    const company = await screen.findByLabelText('고객 회사명')
    await user.type(company, '한 빛')
    expect(company).toHaveValue('한빛')
    expect(await screen.findByText('공백은 입력할 수 없습니다.')).toBeVisible()
  })

  it('checks the email format of the customer on save', async () => {
    const { user } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('고객 이메일'), 'not-an-email')
    await save(user)
    expect(await screen.findByText('이메일 형식이 올바르지 않습니다.')).toBeVisible()
  })
})

describe('Deal 등록 저장 (T-FORM-04)', () => {
  it('fills the contact from the chosen person, saves, and lists the new deal', async () => {
    const { user, location } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('Deal Name'), '신규 등록 테스트')
    await within(screen.getByLabelText('Vendor')).findByRole('option', { name: 'Okta' })
    await user.selectOptions(screen.getByLabelText('Vendor'), 'Okta')
    await pickPerson(user, '고객', '한빛은행', /정민수/)
    expect(screen.getByLabelText('고객 직급')).toHaveValue('과장')
    expect(screen.getByLabelText('고객 이메일')).not.toHaveValue('')
    await user.type(screen.getByLabelText('금액(단위:천원)'), '300000')
    await user.type(screen.getByLabelText('Solution'), 'ITDR')
    await user.type(screen.getByLabelText('Users'), '10')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-05-01' } })
    await save(user)
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))

    const row = await openList(user, '신규 등록 테스트')
    expect(within(row).getByText('한빛은행')).toBeVisible()
    expect(within(row).getByText('김영업')).toBeVisible()
    expect(within(row).getByText('300,000')).toBeVisible()
    expect(within(row).getByRole('button', { name: /Status 편집/ })).toHaveTextContent('기회발굴')
  })

  it('updates the shared contact when the email is corrected on the form', async () => {
    const { user, location } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('Deal Name'), '연락처 갱신 테스트')
    await pickPerson(user, '고객', '한빛은행', /정민수/)
    const email = screen.getByLabelText('고객 이메일')
    await user.clear(email)
    await user.type(email, 'changed.mail@hanbit.test')
    await user.type(screen.getByLabelText('금액(단위:천원)'), '100000')
    await user.type(screen.getByLabelText('Solution'), 'ITDR')
    await user.type(screen.getByLabelText('Users'), '10')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    await save(user)
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))

    const row = await openList(user, '한빛은행 ITDR')
    await user.click(within(row).getByRole('button', { name: /빠른 보기/ }))
    expect(await screen.findByText(/changed\.mail@hanbit\.test/)).toBeVisible()
  })

  it('saves a typed new customer and a BANT label picked from the list', async () => {
    const { user, location } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('Deal Name'), '직접 입력 테스트')
    await user.type(screen.getByLabelText('고객 회사명'), '신규고객사')
    await user.type(screen.getByLabelText('고객 담당자명'), '홍길동')
    await user.click(screen.getByRole('combobox', { name: 'Budget' }))
    await user.click(await screen.findByRole('option', { name: '단독 예산 확보' }))
    await user.type(screen.getByLabelText('금액(단위:천원)'), '50000')
    await user.type(screen.getByLabelText('Solution'), 'ITDR')
    await user.type(screen.getByLabelText('Users'), '10')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    await save(user)
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))

    const row = await openList(user, '직접 입력 테스트')
    expect(within(row).getByText('신규고객사')).toBeVisible()
    await user.click(within(row).getByRole('button', { name: /빠른 보기/ }))
    const view = await screen.findByRole('region', { name: /빠른 보기/ })
    expect(within(view).getByText('홍길동')).toBeVisible()
    expect(within(view).getByText('단독 예산 확보')).toBeVisible()
  })

  it('goes back to the list when cancelled', async () => {
    const { user, location } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.click(screen.getByRole('button', { name: '취소' }))
    expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN)
  })
})
