import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'

async function openLabels(role: 'admin' | 'sales' = 'admin') {
  const view = await renderAt('/admin/deal', { role })
  await view.user.click(await screen.findByRole('tab', { name: 'BANT Label' }))
  await screen.findByRole('region', { name: 'Budget' })
  await screen.findByText('단독 예산 확보')
  return view
}

function section(name: string) {
  return within(screen.getByRole('region', { name }))
}

function labelRow(category: string, name: string) {
  return within(section(category).getByRole('row', { name: new RegExp(name) }))
}

async function addLabel(user: Awaited<ReturnType<typeof renderAt>>['user'], category: string, name: string) {
  await user.type(section(category).getByLabelText('새 Label 이름'), name)
  await user.click(section(category).getByRole('button', { name: '추가' }))
}

describe('BANT Label 관리 목록 (T-LABEL-01, T-ADMIN-06)', () => {
  // BANT 탭은 구분마다 카드를 보이고 그 구분의 기본 Label을 담는다.
  // 테스트 코드: CL-078
  it('shows one section per BANT category with its default labels', async () => {
    // when: BANT Label 탭을 연다 (전제: admin)
    await openLabels()

    // then: Budget·Authority·Need·Timeline 카드마다 자기 구분의 기본 Label만 있다
    for (const category of ['Budget', 'Authority', 'Need', 'Timeline']) {
      expect(screen.getByRole('region', { name: category })).toBeInTheDocument()
    }
    expect(labelRow('Budget', '단독 예산 확보')).toBeTruthy()
    expect(section('Authority').getByText('CEO 보고 완료')).toBeInTheDocument()
    expect(section('Need').getByText('컴플라이언스')).toBeInTheDocument()
    expect(section('Timeline').getByText('금년 구매')).toBeInTheDocument()
    expect(section('Budget').queryByText('CEO 보고 완료')).not.toBeInTheDocument()
  })

  // 기본 Label은 '기본' 배지, 사용 Deal 수, 만든 사람 '시스템'을 보인다.
  // 테스트 코드: CL-078
  it('marks default labels and shows the usage count and who created them', async () => {
    // given: admin이 BANT Label 탭을 연다
    await openLabels()

    // when: 기본 Label 행을 본다
    const row = labelRow('Budget', '단독 예산 확보')
    // then: '기본' 배지·'Deal n건'·'시스템'이 보인다
    expect(row.getByText('기본')).toBeInTheDocument()
    expect(row.getByText(/Deal \d+건/)).toBeInTheDocument()
    expect(row.getByText('시스템')).toBeInTheDocument()
  })

  // 사용자가 만든 Label은 배지 없이 만든 사람과 'Deal 0건'을 보인다.
  // 테스트 코드: CL-078
  it('shows the creator and time of a label made by a user', async () => {
    // given: admin이 BANT Label 탭을 연다
    const { user } = await openLabels()

    // when: Budget에 '분기 예산'을 추가한다
    await addLabel(user, 'Budget', '분기 예산')

    // then: 기본 배지 없이 만든 사람과 'Deal 0건'이 보인다
    const row = labelRow('Budget', '분기 예산')
    expect(await screen.findByText('분기 예산')).toBeInTheDocument()
    expect(row.queryByText('기본')).not.toBeInTheDocument()
    expect(row.getByText(/최관리/)).toBeInTheDocument()
    expect(row.getByText('Deal 0건')).toBeInTheDocument()
  })
})

describe('BANT Label 추가·수정 (T-LABEL-02~03)', () => {
  // Label을 추가하면 그 구분에 나타나고 입력이 비워진다.
  // 테스트 코드: CL-079
  it('adds a label and clears the input', async () => {
    // given: admin이 BANT Label 탭을 연다
    const { user } = await openLabels()

    // when: Need에 '규제 대응'을 추가한다
    await addLabel(user, 'Need', '규제 대응')

    // then: Need 카드에 나타나고 입력은 비어 있다
    expect(await section('Need').findByText('규제 대응')).toBeInTheDocument()
    expect(section('Need').getByLabelText('새 Label 이름')).toHaveValue('')
  })

  // 같은 구분에 대소문자만 다른 이름을 추가하면 서버 문구가 배너에 보인다.
  // 테스트 코드: CL-080
  it('rejects a duplicate name in the same category regardless of case', async () => {
    // given: Need에 'Audit Ready'가 있다
    const { user } = await openLabels()
    await addLabel(user, 'Need', 'Audit Ready')
    await section('Need').findByText('Audit Ready')

    // when: 'audit ready'를 추가한다
    await addLabel(user, 'Need', 'audit ready')

    // then: 중복 문구가 오류 배너에 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('같은 구분에 이미 있는 Label 이름입니다.')
  })

  // 다른 구분에 있는 이름도 추가할 수 있다.
  // 테스트 코드: CL-079
  it('lets the same name exist in a different category', async () => {
    // given: Budget에 '미확인'이 있다
    const { user } = await openLabels()

    // when: Need에 '미확인'을 추가한다
    await addLabel(user, 'Need', '미확인')

    // then: Need에 나타나고 Budget에는 하나뿐이다
    expect(await section('Need').findByText('미확인')).toBeInTheDocument()
    expect(section('Budget').getAllByText('미확인')).toHaveLength(1)
  })

  // 빈 이름과 51자 이름의 추가는 서버 문구를 배너에 보인다.
  // 테스트 코드: CL-080
  it('shows the server messages for an empty and a too long name', async () => {
    // given: admin이 BANT Label 탭을 연다
    const { user } = await openLabels()

    // when: Timeline에서 빈 이름으로, 이어 51자 이름으로 추가한다
    await user.click(section('Timeline').getByRole('button', { name: '추가' }))
    // then: 필수 문구, 이어 길이 문구가 배너에 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('Label 이름을 입력하세요.')

    await addLabel(user, 'Timeline', 'x'.repeat(51))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Label 이름은 50자 이내로 입력하세요.'))
  })

  // 사용 중인 Label도 이름을 바꿀 수 있고 목록에 새 이름이 보인다.
  // 테스트 코드: CL-081
  it('renames a label, including one in use', async () => {
    // given: admin이 BANT Label 탭을 연다
    const { user } = await openLabels()

    // when: '단독 예산 확보'의 이름 수정에서 '전액 예산 확보'로 저장한다
    await user.click(labelRow('Budget', '단독 예산 확보').getByRole('button', { name: '단독 예산 확보' }))
    const input = screen.getByLabelText('Label 이름')
    await user.clear(input)
    await user.type(input, '전액 예산 확보')
    await user.keyboard('{Enter}')

    // then: 새 이름이 보이고 옛 이름은 없다
    expect(await section('Budget').findByText('전액 예산 확보')).toBeInTheDocument()
    expect(section('Budget').queryByText('단독 예산 확보')).not.toBeInTheDocument()
  })

  // 같은 구분의 다른 Label 이름으로 바꾸면 서버 문구가 배너에 보인다.
  // 테스트 코드: CL-081
  it('rejects renaming to a name that already exists in the category', async () => {
    // given: admin이 BANT Label 탭을 연다
    const { user } = await openLabels()

    // when: '단독 예산 확보'를 '풀 예산 확보'로 바꿔 저장한다
    await user.click(labelRow('Budget', '단독 예산 확보').getByRole('button', { name: '단독 예산 확보' }))
    const input = screen.getByLabelText('Label 이름')
    await user.clear(input)
    await user.type(input, '풀 예산 확보')
    await user.keyboard('{Enter}')

    // then: 중복 문구가 오류 배너에 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('같은 구분에 이미 있는 Label 이름입니다.')
  })
})

describe('BANT Label 삭제 (T-LABEL-05)', () => {
  // 쓰이지 않는 Label은 확인 대화상자에서 삭제하면 사라진다.
  // 테스트 코드: CL-082
  it('deletes an unused label after confirmation', async () => {
    // given: Budget에 쓰이지 않는 '임시 Label'을 추가했다
    const { user } = await openLabels()
    await addLabel(user, 'Budget', '임시 Label')
    await section('Budget').findByText('임시 Label')

    // when: 삭제 버튼을 누르고 확인한다
    await user.click(labelRow('Budget', '임시 Label').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog', { name: 'Label 삭제' })).getByRole('button', { name: '삭제' }))

    // then: 목록에서 사라진다
    await waitFor(() => expect(section('Budget').queryByText('임시 Label')).not.toBeInTheDocument())
  })

  // 삭제 확인에서 취소하면 Label이 그대로 남는다.
  // 테스트 코드: CL-082
  it('keeps the label when the confirmation is declined', async () => {
    // given: Budget에 '임시 Label'을 추가했다
    const { user } = await openLabels()
    await addLabel(user, 'Budget', '임시 Label')
    await section('Budget').findByText('임시 Label')

    // when: 삭제 버튼을 누르고 확인 대화상자에서 취소한다
    await user.click(labelRow('Budget', '임시 Label').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '취소' }))

    // then: Label이 그대로 있다
    expect(section('Budget').getByText('임시 Label')).toBeInTheDocument()
  })

  // Deal이 쓰는 Label을 삭제하면 건수가 든 서버 문구가 배너에 보이고 Label은 남는다.
  // 테스트 코드: CL-082
  it('refuses to delete a label that deals use and says how many', async () => {
    // given: admin이 BANT Label 탭을 연다
    const { user } = await openLabels()

    // when: 사용 중인 '단독 예산 확보'를 삭제 확인한다
    await user.click(labelRow('Budget', '단독 예산 확보').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    // then: '(Deal n건)' 문구가 배너에 보이고 Label이 남는다
    expect(await screen.findByRole('alert')).toHaveTextContent(/사용 중인 Label은 삭제할 수 없습니다\. \(Deal \d+건\)/)
    expect(section('Budget').getByText('단독 예산 확보')).toBeInTheDocument()
  })
})

describe('BANT Label 권한 (T-LABEL-04)', () => {
  // sales는 Label을 만들 수 있지만 이름 변경·삭제는 403이다.
  // 테스트 코드: CL-090
  it('lets sales create a label through the gateway but not rename or remove it', async () => {
    // given: sales로 로그인한다
    await renderAt('/deals', { role: 'sales' })
    // when: Label을 만든 뒤 이름 변경·삭제를 요청한다
    const created = await gateway.labels.create('budget', '영업이 만든 Label')

    // then: 이름 변경·삭제는 403으로 거절된다
    await expect(gateway.labels.rename(created.id, '바꾼 이름')).rejects.toMatchObject({ status: 403 })
    await expect(gateway.labels.remove(created.id)).rejects.toMatchObject({ status: 403 })
  })
})

describe('BANT Label 탭 위치', () => {
  // BANT Label 탭은 Status·Forecast 코드 탭 뒤에 놓이고 ?tab=label 주소로 열리면 선택된 탭이다.
  // 테스트 코드: CL-077
  it('opens at ?tab=label as the selected tab right after the code tabs', async () => {
    // given: admin이 ?tab=label 주소로 들어온다
    await openLabels()

    // when: 탭 목록을 읽는다
    const tabs = screen.getAllByRole('tab').map((t) => t.textContent)

    // then: BANT Label 탭이 선택되어 있고 Forecast 코드 탭 바로 뒤, Action 유형 탭 바로 앞이다
    expect(screen.getByRole('tab', { name: 'BANT Label' })).toHaveAttribute('aria-selected', 'true')
    expect(tabs.indexOf('BANT Label')).toBe(tabs.indexOf('Forecast 코드') + 1)
    expect(tabs.indexOf('Action 유형')).toBe(tabs.indexOf('BANT Label') + 1)
  })

  // 탭을 누르면 그 탭이 열리고 주소가 ?tab=label로 바뀐다.
  // 테스트 코드: CL-077
  it('switches to the tab by clicking it and keeps ?tab=label in the address', async () => {
    // given: 탭 없이 Deal 관리 화면을 연다
    const { user, location } = await renderAt('/admin/deal', { role: 'admin' })

    // when: BANT Label 탭을 누른다
    await user.click(await screen.findByRole('tab', { name: 'BANT Label' }))

    // then: Budget 카드가 보이고 주소가 ?tab=label이다
    await screen.findByRole('region', { name: 'Budget' })
    expect(location()).toBe('/admin/deal?tab=label')
  })
})
