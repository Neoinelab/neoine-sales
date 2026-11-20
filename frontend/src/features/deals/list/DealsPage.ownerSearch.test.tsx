import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { resetMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'
import type { SeedData, UserRecord } from '../../../test/fake/store'
import { renderAt } from '../../../test/mockApp'
import { dataRows, rowOf } from './testHelpers'

/**
 * 담당자 자동완성(DL-R40)과 이름 검색(DL-R39) 화면 규칙.
 * 시드 변형: 김영업(kim1)·김영업(kim2) 동명 재직 sales, 이름 없이 아이디만 쓰는 lee, 정관리(jung, 역할이 admin으로 바뀐 재직 Owner),
 * 박영업(park), 한조회(user), 퇴사한 강퇴사(old). 김영업(kim2)은 '세종에너지 ZTNA'를 담당한다.
 */
const NOW = '2026-10-15T09:00:00+09:00'
const KIM2 = 8

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

function ownerSeed(data: SeedData): SeedData {
  const kim = data.users.find((u) => u.id === USER_ID.kim) as UserRecord
  const users = data.users.map((u): UserRecord => {
    // 등록 순서(박영업 → kim2 → kim1)가 이름순(김영업 kim1 → kim2 → 박영업)과 달라 정렬 누락을 잡는다.
    if (u.id === USER_ID.park) return { ...u, createdAt: '2026-01-01T09:00:00+09:00' }
    if (u.id === USER_ID.kim) return { ...u, loginId: 'kim1', createdAt: '2026-01-03T09:00:00+09:00' }
    if (u.id === USER_ID.lee) return { ...u, name: 'lee' }
    if (u.id === USER_ID.jung) return { ...u, name: '정관리', role: 'admin' }
    return u
  })
  users.push({ ...kim, id: KIM2, loginId: 'kim2', createdAt: '2026-01-02T09:00:00+09:00' })
  const deals = data.deals.map((d) => (d.name === '세종에너지 ZTNA' ? { ...d, ownerId: KIM2 } : d))
  return { ...data, users, deals }
}

const open = (url: string, role: 'sales' | 'admin' = 'sales') => renderAt(url, { role, adjustSeed: ownerSeed })
/** 담당자 입력 칸. 예전 선택 상자(select)도 combobox 역할이라 입력 칸(INPUT)인지 함께 확인한다. */
const box = () => screen.getByRole('combobox', { name: '담당자' }) as HTMLInputElement
const owner = async () => {
  await screen.findByRole('combobox', { name: '담당자' })
  expect(box().tagName).toBe('INPUT')
  return box()
}
const searchOf = (location: () => string) => new URLSearchParams(location().split('?')[1] ?? '')
const lastQuery = (spy: ReturnType<typeof vi.spyOn>) => spy.mock.calls.at(-1)?.[0] as Record<string, unknown>
const candidates = () => within(screen.getByRole('listbox', { name: '담당자' })).getAllByRole('option')
const NO_ROWS = '조건에 맞는 Deal이 없습니다.'
const settle = () => new Promise((resolve) => setTimeout(resolve, 50))

describe('담당자 후보', () => {
  // 담당자 칸은 콤보박스이고 재직 sales만 한 사람씩 "이름 (아이디)"로 이름순 후보에 보이며 입력으로 걸러진다
  // 테스트 코드: DL-136
  it('shows only active sales as name and login id candidates and filters them by the typed letters', async () => {
    // given: 재직 sales·admin·user와 퇴사 sales가 있는 Fake, 담당자 조건이 없는 목록
    const { user } = await open('/deals?year=all')

    // when: 담당자 칸을 누르고, "박"을 입력하고, "강"을 입력한다
    await owner()
    await user.click(box())
    await screen.findByRole('listbox', { name: '담당자' })
    const all = candidates()
    const allNames = all.map((o) => o.textContent)
    await user.clear(box())
    await user.type(box(), '박')
    const park = candidates().map((o) => o.textContent)
    await user.clear(box())
    await user.type(box(), '강')

    // then: 칸은 이름 "담당자"인 입력 combobox이고 placeholder가 있다
    expect(box()).toHaveAttribute('placeholder', '이름 입력')
    // then: 빈 칸에서는 재직 sales만 이름순으로 보이고 admin·user·퇴사자는 없다
    expect(allNames.filter((n) => n?.startsWith('김영업') || n === '박영업 (park)')).toEqual(['김영업 (kim1)', '김영업 (kim2)', '박영업 (park)'])
    expect(allNames).toContain('lee')
    expect(allNames).toHaveLength(4)
    expect(allNames.join('|')).not.toMatch(/정관리|한조회|최관리|강퇴사/)
    for (const option of all) expect(option).toHaveAccessibleName(option.textContent ?? '')
    // then: "박"에서는 박영업 하나, "강"에서는 목록도 오류 문구도 없다
    expect(park).toEqual(['박영업 (park)'])
    await waitFor(() => expect(screen.queryByRole('listbox')).not.toBeInTheDocument())
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // 후보는 아이디 글자로도 걸러지지만 고르지 않고 아이디로 검색하면 이름 기준이라 0건이다
  // 테스트 코드: DL-137
  it('filters candidates by login id but searches by name, so a bare login id finds nothing', async () => {
    // given: kim2가 Deal을 가진 Fake, 담당자 조건이 없는 목록
    const { user, location } = await open('/deals?year=all')
    await rowOf(/세종에너지 ZTNA/)
    await owner()

    // when: 담당자 칸에 "kim2"를 입력하고 후보를 고르지 않은 채 "검색"을 누른다
    await user.type(box(), 'kim2')
    await screen.findByRole('listbox', { name: '담당자' })
    const options = candidates().map((o) => o.textContent)
    await user.click(screen.getByRole('button', { name: '검색' }))

    // then: 입력 중 후보는 "김영업 (kim2)" 하나이고, 검색 뒤 URL은 owner_name이며 오류 없이 0건 문구가 보인다
    expect(options).toEqual(['김영업 (kim2)'])
    await waitFor(() => expect(searchOf(location).get('owner_name')).toBe('kim2'))
    expect(searchOf(location).has('owner')).toBe(false)
    expect(await screen.findByText(NO_ROWS)).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('담당자 후보 고르기', () => {
  // 후보를 고르면 즉시 URL owner가 그 사람 id가 되어 그 한 사람의 Deal만 보이고 Esc는 목록만 닫는다
  // 테스트 코드: DL-138
  it('selects one person at once by owner id and only closes the list on Escape', async () => {
    // given: owner_name과 page가 있는 주소, 요청을 관찰한다
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location } = await open('/deals?year=all&owner_name=영업&page=2')
    await owner()
    await user.type(screen.getByLabelText('키워드'), 'ERP')

    // when: 칸을 지우고 "김"을 입력해 ↓·↓·Enter로 "김영업 (kim2)"를 고른다
    await user.clear(box())
    await user.type(box(), '김')
    await screen.findByRole('listbox', { name: '담당자' })
    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}')

    // then: URL은 owner=<kim2 id>만 남고(owner_name·page·키워드 없음) 요청은 ownerId이며 kim2의 Deal만 보인다
    await waitFor(() => expect(location()).toBe(`/deals?year=all&owner=${KIM2}`))
    await waitFor(() => expect(lastQuery(list).ownerId).toBe(KIM2))
    expect(lastQuery(list).ownerName).toBeUndefined()
    expect(await rowOf(/세종에너지 ZTNA/)).toBeVisible()
    expect(dataRows()).toHaveLength(1)
    expect(box()).toHaveValue('김영업 (kim2)')

    // when: 칸을 지우고 "박"을 입력해 목록이 열린 채 Esc를 누른다
    await user.clear(box())
    await user.type(box(), '박')
    await screen.findByRole('listbox', { name: '담당자' })
    const calls = list.mock.calls.length
    await user.keyboard('{Escape}')
    await settle()

    // then: 목록만 닫히고 URL·요청은 그대로다
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(location()).toBe(`/deals?year=all&owner=${KIM2}`)
    expect(list.mock.calls).toHaveLength(calls)
  })
})

describe('담당자 직접 입력', () => {
  // 글자만 입력하고 검색하면 owner_name으로 키워드와 함께 반영되고 후보가 없던 글자·"이름(퇴사)"도 그대로 검색된다
  // 테스트 코드: DL-139
  it('searches by typed letters with the keyword, including a resigned name and an unknown name', async () => {
    // given: owner=박영업이 걸린 주소, 요청을 관찰한다
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location } = await open(`/deals?year=all&owner=${USER_ID.park}`)
    await owner()
    await waitFor(() => expect(box()).toHaveValue('박영업 (park)'))

    // when: 키워드 "한빛은행", 담당자 "  김영 "을 입력하고 "검색"을 누른다
    await user.type(screen.getByLabelText('키워드'), '한빛은행')
    await user.clear(box())
    await user.type(box(), '  김영 ')
    await user.click(screen.getByRole('button', { name: '검색' }))

    // then: URL에 q와 owner_name이 있고 owner는 없으며 김영업의 한빛은행 Deal만 조회된다
    await waitFor(() => expect(searchOf(location).get('owner_name')).toBe('김영'))
    expect(searchOf(location).get('q')).toBe('한빛은행')
    expect(searchOf(location).has('owner')).toBe(false)
    expect(lastQuery(list)).toMatchObject({ ownerName: '김영', keyword: '한빛은행' })
    expect(lastQuery(list).ownerId).toBeUndefined()
    expect(await rowOf(/한빛은행 ITDR 도입/)).toBeVisible()
    expect(screen.queryByRole('row', { name: /한빛은행 PAM/ })).not.toBeInTheDocument()

    // when: 퇴사자 표기 "강퇴사(퇴사)"를 입력하고 Enter를 누른다
    await user.clear(box())
    await user.type(box(), '강퇴사(퇴사)')
    const listboxWhileTyping = screen.queryByRole('listbox')
    await user.keyboard('{Enter}')

    // then: owner_name이 그 글자이고 퇴사자의 Deal만 보이며 입력 중 후보 목록은 없었다
    expect(listboxWhileTyping).toBeNull()
    await waitFor(() => expect(searchOf(location).get('owner_name')).toBe('강퇴사(퇴사)'))
    expect(await rowOf(/한빛은행 PAM/)).toBeVisible()
    expect(dataRows()).toHaveLength(1)

    // when: 맞는 사람이 없는 "없는사람"을 입력하고 검색한다
    await user.clear(box())
    await user.type(box(), '없는사람')
    await user.click(screen.getByRole('button', { name: '검색' }))

    // then: owner_name이 그 글자이고 오류 없이 0건 문구가 보인다
    await waitFor(() => expect(searchOf(location).get('owner_name')).toBe('없는사람'))
    expect(await screen.findByText(NO_ROWS)).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // 담당자 칸을 비우기만 하면 URL이 그대로이고 검색하면 owner·owner_name이 모두 지워진다
  // 테스트 코드: DL-140
  it.each([
    ['owner', `/deals?year=all&owner=${USER_ID.park}`],
    ['owner_name', '/deals?year=all&owner_name=영업'],
  ])('clears the %s condition only on search, not when the input is just emptied', async (_key, url) => {
    // given: 담당자 조건이 걸린 주소, 요청을 관찰한다
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location } = await open(url)
    await owner()
    await waitFor(() => expect(box()).not.toHaveValue(''))
    await settle()
    const calls = list.mock.calls.length
    const before = location()

    // when: 칸 글자를 모두 지운다
    await user.clear(box())
    await settle()

    // then: URL과 요청은 그대로다
    expect(location()).toBe(before)
    expect(list.mock.calls).toHaveLength(calls)

    // when: "검색"을 누른다
    await user.click(screen.getByRole('button', { name: '검색' }))

    // then: URL에서 owner·owner_name이 모두 사라지고 모든 담당자의 Deal이 조회된다
    await waitFor(() => expect(location()).toBe('/deals?year=all'))
    expect(lastQuery(list).ownerId).toBeUndefined()
    expect(lastQuery(list).ownerName).toBeUndefined()
    await rowOf(/미래전자 EDR 교체/)
    await rowOf(/한빛은행 ITDR 도입/)
  })
})

describe('담당자 고른 뒤 고치지 않은 검색', () => {
  // 후보를 고른 뒤 칸 끝에 공백을 넣거나 대소문자만 바꿔 검색해도 고른 사람(owner)이 유지된다(DL-R40 규칙 2)
  // 테스트 코드: DL-145
  it.each([
    ['끝 공백', '김영업 (kim2) '],
    ['대소문자만 다름', '김영업 (KIM2)'],
  ])('keeps the chosen owner id when the input differs only by %s', async (_label, typed) => {
    // given: 후보 "김영업 (kim2)"를 고른 목록
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location } = await open('/deals?year=all')
    await owner()
    await user.type(box(), 'kim2')
    await user.click(await screen.findByRole('option', { name: '김영업 (kim2)' }))
    await waitFor(() => expect(searchOf(location).get('owner')).toBe(String(KIM2)))

    // when: 칸을 공백·대소문자만 다르게 고치고 "검색"을 누른다
    await user.clear(box())
    await user.type(box(), typed)
    await user.click(screen.getByRole('button', { name: '검색' }))
    await settle()

    // then: URL은 owner=<kim2 id>를 유지하고 owner_name은 없으며 요청은 ownerId다
    expect(searchOf(location).get('owner')).toBe(String(KIM2))
    expect(searchOf(location).has('owner_name')).toBe(false)
    expect(lastQuery(list).ownerId).toBe(KIM2)
    expect(lastQuery(list).ownerName).toBeUndefined()
  })
})

describe('URL owner_name 길이 한도', () => {
  // URL의 owner_name이 100자를 넘으면 조회에 쓰지 않고 칸도 비운다
  // 테스트 코드: DL-146
  it('ignores an owner_name over 100 characters and leaves the input empty', async () => {
    // given: 요청을 관찰한다
    const list = vi.spyOn(gateway.deals, 'list')

    // when: 101자 owner_name이 든 주소로 연다
    await open(`/deals?owner_name=${'가'.repeat(101)}`, 'admin')
    const input = await owner()
    await waitFor(() => expect(list).toHaveBeenCalled())
    await settle()

    // then: 요청에 ownerName이 없고(조건 없음) 칸도 비어 있다
    expect(lastQuery(list).ownerName).toBeUndefined()
    expect(lastQuery(list).ownerId).toBeUndefined()
    expect(input).toHaveValue('')
  })

  // 100자 owner_name은 그대로 칸에 보이고 조회에 쓴다(경계값)
  // 테스트 코드: DL-146
  it('keeps an owner_name of exactly 100 characters in the input and in the request', async () => {
    // given: 요청을 관찰한다
    const list = vi.spyOn(gateway.deals, 'list')
    const text = '가'.repeat(100)

    // when: 100자 owner_name이 든 주소로 연다
    await open(`/deals?owner_name=${text}`, 'admin')

    // then: 칸 글자와 요청 조건이 그 100자다
    expect(await owner()).toHaveValue(text)
    await waitFor(() => expect(lastQuery(list).ownerName).toBe(text))
  })
})

describe('담당자 URL 복원', () => {
  // owner=<id> 주소는 칸에 그 사용자 표시 글자로 보이고 고치지 않고 검색하면 owner가 유지된다
  // 테스트 코드: DL-141, DL-071
  it.each([
    ['퇴사자', USER_ID.old, '강퇴사(퇴사)'],
    ['동명 재직 sales', KIM2, '김영업 (kim2)'],
    ['역할이 바뀐 재직 Owner', USER_ID.jung, '정관리 (jung)'],
  ])('shows %s by display text and keeps owner when searched without editing the input', async (_label, id, text) => {
    // given: owner=<id> 주소, 요청을 관찰한다
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location } = await open(`/deals?year=all&owner=${id}`)
    await owner()

    // when: 담당자 칸을 고치지 않고 키워드만 입력해 검색한다
    await waitFor(() => expect(box()).toHaveValue(text))
    await user.type(screen.getByLabelText('키워드'), 'ERP')
    await user.click(screen.getByRole('button', { name: '검색' }))

    // then: 칸 글자는 그대로이고 URL은 owner를 유지하며 owner_name은 없고 q가 더해진다
    await waitFor(() => expect(searchOf(location).get('q')).toBe('ERP'))
    expect(searchOf(location).get('owner')).toBe(String(id))
    expect(searchOf(location).has('owner_name')).toBe(false)
    expect(box()).toHaveValue(text)
    expect(lastQuery(list)).toMatchObject({ ownerId: id })
  })

  // 목록에 없는 id는 "선택한 담당자"로 보이고 요청에는 그 id가 있다
  // 테스트 코드: DL-141
  it('shows an unknown owner id as the selected owner and still sends the id', async () => {
    // given: 없는 id가 든 주소, 요청을 관찰한다
    const list = vi.spyOn(gateway.deals, 'list')

    // when: 목록을 연다
    await open('/deals?year=all&owner=999999')

    // then: 칸 글자는 "선택한 담당자"이고 요청에 그 id가 있다
    expect(await owner()).toHaveValue('선택한 담당자')
    await waitFor(() => expect(lastQuery(list).ownerId).toBe(999999))
  })

  // 사용자 목록을 못 읽으면 "선택한 담당자"로 보이고 오류 배너가 있으며 칸은 입력할 수 있다
  // 테스트 코드: DL-141
  it('shows the selected owner text with an error banner when the user options cannot be read', async () => {
    // given: 사용자 선택 목록 조회가 실패하는 Fake
    const failure = new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: '사용자 목록을 불러오지 못했습니다.' })
    vi.spyOn(gateway.users, 'options').mockRejectedValue(failure)
    const list = vi.spyOn(gateway.deals, 'list')

    // when: owner=<id> 주소를 연다
    const { user } = await open(`/deals?year=all&owner=${USER_ID.park}`)

    // then: 필터 오류 배너가 보이고 칸 글자는 "선택한 담당자"이며 요청에 id가 있고 입력할 수 있다
    expect(await screen.findByRole('alert')).toBeVisible()
    expect(await owner()).toHaveValue('선택한 담당자')
    await waitFor(() => expect(lastQuery(list).ownerId).toBe(USER_ID.park))
    await user.clear(box())
    await user.type(box(), '김')
    expect(box()).toHaveValue('김')
  })

  // owner와 owner_name이 함께 있으면 owner_name만 칸과 요청에 쓴다
  // 테스트 코드: DL-141
  it('uses only owner_name when both owner and owner_name are in the url', async () => {
    // given: 둘 다 있는 주소, 요청을 관찰한다
    const list = vi.spyOn(gateway.deals, 'list')

    // when: 목록을 연다
    await open(`/deals?year=all&owner=${USER_ID.park}&owner_name=김`)

    // then: 칸 글자는 "김"이고 요청에는 ownerName만 있다
    expect(await owner()).toHaveValue('김')
    await waitFor(() => expect(lastQuery(list).ownerName).toBe('김'))
    expect(lastQuery(list).ownerId).toBeUndefined()
  })

  // URL owner_name은 칸·활성 필터·조건 기억에 쓰이고 뒤로 가기·초기화를 따른다
  // 테스트 코드: DL-142
  it('uses owner_name as an active filter, remembers it, and follows back navigation and reset', async () => {
    // given: admin이 owner_name만 있는 주소를 연다(다른 조건 없음), 요청을 관찰한다
    const list = vi.spyOn(gateway.deals, 'list')
    const { user, location, goTo } = await open('/deals?owner_name=영업', 'admin')
    await owner()

    // then: 칸은 "영업"이고 기본 조건(year)으로 바뀌지 않으며 요청에 ownerName이 있다
    expect(box()).toHaveValue('영업')
    await waitFor(() => expect(lastQuery(list).ownerName).toBe('영업'))
    expect(searchOf(location).has('year')).toBe(false)

    // when: 칸을 "아무개"로 고친 뒤(검색하지 않고) 지우고 "박"을 입력해 후보 "박영업 (park)"을 고른다
    await user.clear(box())
    await user.type(box(), '아무개')
    await user.clear(box())
    await user.type(box(), '박')
    await user.click(await screen.findByRole('option', { name: '박영업 (park)' }))

    // then: URL은 owner=<park id>이고 칸은 "박영업 (park)"이다
    await waitFor(() => expect(searchOf(location).get('owner')).toBe(String(USER_ID.park)))
    expect(searchOf(location).has('owner_name')).toBe(false)
    expect(box()).toHaveValue('박영업 (park)')

    // when: 뒤로 가기를 한다
    goTo(-1)

    // then: owner_name=영업과 "영업"으로 돌아가고 "아무개"는 남지 않는다
    await waitFor(() => expect(searchOf(location).get('owner_name')).toBe('영업'))
    expect(box()).toHaveValue('영업')

    // when: 상세에 다녀온다(← 목록 링크)
    await waitFor(() => expect(dataRows().length).toBeGreaterThan(0))
    await user.click(within(dataRows()[0] as HTMLElement).getAllByRole('link')[0] as HTMLElement)
    await user.click(await screen.findByRole('link', { name: '← 목록' }))

    // then: 목록이 owner_name=영업으로 복원된다(조건 기억)
    await screen.findByRole('search', { name: 'Deal 필터' })
    expect(searchOf(location).get('owner_name')).toBe('영업')
    expect(await owner()).toHaveValue('영업')

    // when: "초기화"를 누른다
    await user.click(screen.getByRole('button', { name: '초기화' }))

    // then: 담당자 칸이 비고 URL에 담당자 조건이 없다
    await waitFor(() => expect(location()).toBe('/deals?year=all'))
    expect(await owner()).toHaveValue('')
  })
})
