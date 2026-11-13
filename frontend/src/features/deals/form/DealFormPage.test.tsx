import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { AMOUNT_INPUT_MESSAGE, AMOUNT_TOO_LARGE_MESSAGE } from '../../../shared/model/money'
import { renderAt } from '../../../test/mockApp'
import { DETAIL_URL, openList, pickPerson, save } from './testHelpers'
import { defaultDealsUrlPattern } from '../../../test/dealsUrl'

afterEach(() => vi.restoreAllMocks())

describe('Deal 등록 기본값 (T-FORM-02, T-FORM-03)', () => {
  // 등록 폼은 로그인 sales를 Owner로, 기회발굴·Pipeline으로 시작한다.
  // 테스트 코드: DE-073
  it('starts with the signed-in sales user as owner, 기회발굴 and Pipeline', async () => {
    // when: Deal 등록 화면을 연다.
    await renderAt('/deals/new')
    // then: Owner가 김영업, Status 기회발굴, Forecast Pipeline이고 통화 KRW와 금액 칸이 보인다.
    expect(await screen.findByRole('heading', { name: 'Deal 등록' })).toBeVisible()
    await waitFor(() => expect(screen.getByLabelText('Owner')).toHaveDisplayValue('김영업'))
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('기회발굴')
    expect(screen.getByLabelText('Forecast')).toHaveDisplayValue('Pipeline')
    expect(screen.getByText('KRW')).toBeVisible()
    expect(screen.getByLabelText('금액(단위:원)')).toBeVisible()
  })

  // Owner 후보는 재직 sales만이다.
  // 테스트 코드: DE-074
  it('offers only active sales users as owner candidates', async () => {
    // when: Deal 등록 화면을 연다.
    await renderAt('/deals/new')
    const owner = await screen.findByLabelText('Owner')
    await within(owner).findByRole('option', { name: '박영업' })
    const names = within(owner)
      .getAllByRole('option')
      .map((o) => o.textContent)
    // then: '선택하세요'와 재직 sales 4명만 후보다.
    expect(names).toEqual(['선택하세요', '김영업', '박영업', '이영업', '정영업'])
  })

  // admin이 열면 Owner가 비어 있다.
  // 테스트 코드: DE-074
  it('leaves the owner empty for an admin, who is not a sales user', async () => {
    // given: admin으로 로그인했다.
    await renderAt('/deals/new', { role: 'admin' })
    const owner = await screen.findByLabelText('Owner')
    // when: Deal 등록 화면을 연다.
    await within(owner).findByRole('option', { name: '김영업' })
    // then: Owner가 '선택하세요'다.
    expect(owner).toHaveDisplayValue('선택하세요')
  })

  // Status 7개·Forecast 6개 선택지가 모두 있다.
  // 테스트 코드: DE-075
  it('lists all seven Status values and all six Forecast values', async () => {
    // when: Deal 등록 화면을 연다.
    await renderAt('/deals/new')
    const status = await screen.findByLabelText('Status')
    await within(status).findByRole('option', { name: '계약완료' })
    // then: Status 선택지 7개, Forecast 선택지 6개다.
    expect(within(status).getAllByRole('option')).toHaveLength(7)
    expect(within(screen.getByLabelText('Forecast')).getAllByRole('option')).toHaveLength(6)
  })
})

describe('필수 입력과 오류 문구 (T-FORM-01, T-FORM-05)', () => {
  // 빈 폼을 저장하면 필수 문구를 한꺼번에 보이고 첫 잘못된 칸으로 포커스한다.
  // 테스트 코드: DE-077
  it('shows every required message at once and focuses the first invalid input', async () => {
    // when: 아무것도 입력하지 않고 저장한다.
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await save(user)
    const alerts = (await screen.findAllByRole('alert')).map((a) => a.textContent)
    // then: 필수 문구가 한꺼번에 나오고 Deal Name 칸이 포커스를 받는다.
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
    expect(create).not.toHaveBeenCalled() // 요청을 보내지 않는 것이 사용자 결과다
    expect(location()).toBe('/deals/new')
  })

  // 금액이 상한을 넘으면 막는다.
  // 테스트 코드: DE-078
  it('rejects an amount over the maximum', async () => {
    // when: 금액에 2^53(상한+1)을 입력하고 저장한다.
    const { user } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('금액(단위:원)'), '9007199254740992')
    await save(user)
    // then: 상한 초과 문구가 나온다.
    expect(await screen.findByText(AMOUNT_TOO_LARGE_MESSAGE)).toBeVisible()
  })

  // 금액은 콤마로 보이고 원 단위 안내가 있다.
  // 테스트 코드: DE-078
  it('shows the won hint and keeps the typed won amount as commas', async () => {
    // given: Deal 등록 화면이다.
    const { user } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    // then: 원 단위 안내가 보인다.
    expect(screen.getByText('원 단위 정수(예: 1억 원 = 100,000,000)')).toBeVisible()
    // when: 금액에 1870000000을 입력한다.
    await user.type(screen.getByLabelText('금액(단위:원)'), '1870000000')
    // then: 칸 값이 1,870,000,000이다.
    expect(screen.getByLabelText('금액(단위:원)')).toHaveValue('1,870,000,000')
  })

  // 입력한 금액이 그대로 저장된다.
  // 테스트 코드: DE-078
  it('saves the typed won amount as is', async () => {
    // given: 필수 값을 입력했다.
    const { user, location } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('Deal Name'), '원 단위 저장')
    await pickPerson(user, '고객', '한빛은행', /정민수/)
    await user.type(screen.getByLabelText('Solution'), 'ITDR')
    await user.type(screen.getByLabelText('Users count'), '10')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    // when: 금액 1870000000으로 저장한다.
    await user.type(screen.getByLabelText('금액(단위:원)'), '1870000000')
    await save(user)
    // then: 상세로 이동하고 저장된 Deal의 금액이 1,870,000,000이다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const saved = await gateway.deals.get(location().replace('/deals/', ''))
    expect(saved.revenueAmount).toBe(1_870_000_000)
  })

  // 상한(2^53-1)은 허용한다.
  // 테스트 코드: DE-078
  it('accepts the maximum safe amount without the too-large message', async () => {
    // when: 금액에 2^53-1을 입력하고 저장한다.
    const { user } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('금액(단위:원)'), '9007199254740991')
    // then: 콤마 표기로 보이고 상한 초과 문구는 나오지 않는다.
    expect(screen.getByLabelText('금액(단위:원)')).toHaveValue('9,007,199,254,740,991')
    await save(user)
    await screen.findByText('Deal Name을 입력하세요.')
    expect(screen.queryByText(AMOUNT_TOO_LARGE_MESSAGE)).not.toBeInTheDocument()
  })

  // 금액 0은 막는다.
  // 테스트 코드: DE-078
  it('rejects a zero amount', async () => {
    // when: 금액에 0을 입력하고 저장한다.
    const { user } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('금액(단위:원)'), '0')
    await save(user)
    // then: 금액 입력 문구가 나온다.
    expect(await screen.findByText(AMOUNT_INPUT_MESSAGE)).toBeVisible()
  })

  // Owner 미선택·음수 Users count는 막는다.
  // 테스트 코드: DE-079
  it('asks for the owner when none is chosen and for a non-negative Users count number', async () => {
    // given: admin이라 Owner가 비어 있다.
    const { user } = await renderAt('/deals/new', { role: 'admin' })
    await screen.findByRole('heading', { name: 'Deal 등록' })
    // when: Users count에 -1을 입력하고 저장한다.
    await user.type(screen.getByLabelText('Users count'), '-1')
    await save(user)
    // then: Owner 선택 문구와 Users count 문구가 나온다.
    expect(await screen.findByText('Owner를 선택하세요.')).toBeVisible()
    expect(screen.getByText('Users count는 0 이상의 정수로 입력하세요.')).toBeVisible()
  })

  // Users count가 비면 요청 없이 문구를 보인다.
  // 테스트 코드: DE-079
  it('asks for Users count when it is left empty and does not call the gateway', async () => {
    // given: Deal 등록 화면이다.
    const create = vi.spyOn(gateway.deals, 'create')
    const { user, location } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    // when: Users count만 비우고 나머지 필수 값을 입력해 저장한다.
    await user.type(screen.getByLabelText('Deal Name'), 'Users count 비움')
    await pickPerson(user, '고객', '한빛은행', /정민수/)
    await user.type(screen.getByLabelText('금액(단위:원)'), '100000000')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    await save(user)
    // then: Users count 필수 문구가 나오고 등록 요청이 없으며 화면이 그대로다.
    expect(await screen.findByText('Users count를 입력하세요.')).toBeVisible()
    expect(create).not.toHaveBeenCalled()
    expect(location()).toBe('/deals/new')
  })

  // Users count 0은 저장한다.
  // 테스트 코드: DE-079
  it('saves Users count of zero', async () => {
    // given: 필수 값을 입력했다.
    const { user, location } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('Deal Name'), 'Users count 영')
    await pickPerson(user, '고객', '한빛은행', /정민수/)
    await user.type(screen.getByLabelText('금액(단위:원)'), '100000000')
    await user.type(screen.getByLabelText('Solution'), 'ITDR')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    // when: Users count 0으로 저장한다.
    await user.type(screen.getByLabelText('Users count'), '0')
    await save(user)
    // then: 상세로 이동하고 저장된 Users count가 0이다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    const saved = await gateway.deals.get(location().replace('/deals/', ''))
    expect(saved.users).toBe(0)
  })

  // 파트너 입력을 시작하면 회사명·담당자명이 모두 필요하다.
  // 테스트 코드: DE-081
  it('requires both company and name once a partner is started', async () => {
    // when: 파트너 회사명만 입력하고 저장한다.
    const { user } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('파트너 회사명'), '코어테크')
    await save(user)
    // then: 파트너 반쪽 입력 문구가 나온다.
    expect(await screen.findByText('파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.')).toBeVisible()
  })

  // 파트너를 비워 두면 묻지 않는다.
  // 테스트 코드: DE-081
  it('does not ask anything about the partner when it is left empty', async () => {
    // when: 아무것도 입력하지 않고 저장한다.
    const { user } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await save(user)
    await screen.findAllByRole('alert')
    // then: 다른 필수 문구는 나오지만 파트너 문구는 없다.
    expect(screen.queryByText(/파트너를 입력하면/)).not.toBeInTheDocument()
  })

  // 고객 회사명의 공백은 지워지고 이유를 알린다.
  // 테스트 코드: DE-082
  it('removes spaces typed into the customer company and explains why', async () => {
    // when: 고객 회사명에 '한 빛'을 입력한다.
    const { user } = await renderAt('/deals/new')
    const company = await screen.findByLabelText('고객 회사명')
    await user.type(company, '한 빛')
    // then: 칸 값이 '한빛'이고 '공백은 입력할 수 없습니다.'가 나온다.
    expect(company).toHaveValue('한빛')
    expect(await screen.findByText('공백은 입력할 수 없습니다.')).toBeVisible()
  })

  // 고객 이메일 형식을 저장 때 알린다.
  // 테스트 코드: DE-082
  it('checks the email format of the customer on save', async () => {
    // when: 고객 이메일에 형식이 틀린 값을 입력하고 저장한다.
    const { user } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('고객 이메일'), 'not-an-email')
    await save(user)
    // then: 이메일 형식 문구가 나온다.
    expect(await screen.findByText('이메일 형식이 올바르지 않습니다.')).toBeVisible()
  })
})

describe('Deal 등록 저장 (T-FORM-04)', () => {
  // 담당자를 골라 채운 뒤 저장하면 새 Deal이 목록에 나온다.
  // 테스트 코드: DE-083
  it('fills the contact from the chosen person, saves, and lists the new deal', async () => {
    // given: Deal 등록 화면이다.
    const { user, location } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    // when: Vendor와 고객 담당자를 고른다.
    await user.type(screen.getByLabelText('Deal Name'), '신규 등록 테스트')
    await within(screen.getByLabelText('Vendor')).findByRole('option', { name: 'Okta' })
    await user.selectOptions(screen.getByLabelText('Vendor'), 'Okta')
    await pickPerson(user, '고객', '한빛은행', /정민수/)
    // then: 직급·이메일이 채워진다.
    expect(screen.getByLabelText('고객 직급')).toHaveValue('과장')
    expect(screen.getByLabelText('고객 이메일')).not.toHaveValue('')

    // when: 나머지 필수 값을 넣고 저장한다.
    await user.type(screen.getByLabelText('금액(단위:원)'), '300000000')
    await user.type(screen.getByLabelText('Solution'), 'ITDR')
    await user.type(screen.getByLabelText('Users count'), '10')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-05-01' } })
    await save(user)
    // then: 상세로 이동한다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))

    // when: 목록에서 새 Deal 행을 찾는다.
    const row = await openList(user, '신규 등록 테스트')
    // then: 행에 고객·Owner·금액·Status가 보인다.
    expect(within(row).getByText('한빛은행')).toBeVisible()
    expect(within(row).getByText('김영업')).toBeVisible()
    expect(within(row).getByText('300,000,000')).toBeVisible()
    expect(within(row).getByRole('button', { name: /Status 편집/ })).toHaveTextContent('기회발굴')
  })

  // 폼에서 고른 고객의 이메일을 고치면 공유 연락처가 갱신된다.
  // 테스트 코드: DE-084
  it('updates the shared contact when the email is corrected on the form', async () => {
    // given: Deal 등록 화면이다.
    const { user, location } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    // when: 고른 고객의 이메일을 고쳐 저장한다.
    await user.type(screen.getByLabelText('Deal Name'), '연락처 갱신 테스트')
    await pickPerson(user, '고객', '한빛은행', /정민수/)
    const email = screen.getByLabelText('고객 이메일')
    await user.clear(email)
    await user.type(email, 'changed.mail@hanbit.test')
    await user.type(screen.getByLabelText('금액(단위:원)'), '100000000')
    await user.type(screen.getByLabelText('Solution'), 'ITDR')
    await user.type(screen.getByLabelText('Users count'), '10')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    await save(user)
    // then: 상세로 이동한다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))

    // when: 같은 고객을 쓰는 Deal의 빠른 보기를 연다.
    const row = await openList(user, '한빛은행 ITDR')
    await user.click(within(row).getByRole('button', { name: /빠른 보기/ }))
    // then: 고친 이메일이 보인다.
    expect(await screen.findByText(/changed\.mail@hanbit\.test/)).toBeVisible()
  })

  // 새로 입력한 고객과 목록에서 고른 BANT로 등록된다.
  // 테스트 코드: DE-085
  it('saves a typed new customer and a BANT label picked from the list', async () => {
    // given: Deal 등록 화면이다.
    const { user, location } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    // when: 새 고객과 Budget Label을 골라 저장한다.
    await user.type(screen.getByLabelText('Deal Name'), '직접 입력 테스트')
    await user.type(screen.getByLabelText('고객 회사명'), '신규고객사')
    await user.type(screen.getByLabelText('고객 담당자명'), '홍길동')
    await user.click(screen.getByRole('combobox', { name: 'Budget' }))
    await user.click(await screen.findByRole('option', { name: '단독 예산 확보' }))
    await user.type(screen.getByLabelText('금액(단위:원)'), '50000000')
    await user.type(screen.getByLabelText('Solution'), 'ITDR')
    await user.type(screen.getByLabelText('Users count'), '10')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-06-01' } })
    await save(user)
    // then: 상세로 이동한다.
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))

    // when: 목록에서 그 행을 찾고 빠른 보기를 연다.
    const row = await openList(user, '직접 입력 테스트')
    // then: 목록 행에 새 고객사가 보인다.
    expect(within(row).getByText('신규고객사')).toBeVisible()

    // when: 빠른 보기를 연다.
    await user.click(within(row).getByRole('button', { name: /빠른 보기/ }))
    // then: 빠른 보기에 담당자와 고른 Label이 보인다.
    const view = await screen.findByRole('region', { name: /빠른 보기/ })
    expect(within(view).getByText('홍길동')).toBeVisible()
    expect(within(view).getByText('단독 예산 확보')).toBeVisible()
  })

  // 취소하면 등록은 목록으로 간다.
  // 테스트 코드: DE-106
  it('goes back to the list when cancelled', async () => {
    // when: 등록 화면에서 취소를 누른다.
    const { user, location } = await renderAt('/deals/new')
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.click(screen.getByRole('button', { name: '취소' }))
    // then: Deals 목록 주소로 이동한다.
    expect(location()).toMatch(defaultDealsUrlPattern('sales'))
  })
})
