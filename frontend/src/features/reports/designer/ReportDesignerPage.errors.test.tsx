import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ApiError } from '../../../shared/api/problem'
import type { ReportIssue } from '../../../shared/model/reportTypes'
import { mockControl } from '../../../test/fake/default'
import { invalidReport, REPORT_TIMEOUT_MESSAGE, reportTimeout } from '../../../test/fake/errors'
import {
  addColumn,
  addCondition,
  chipButton,
  chipItems,
  lastQuery,
  openDesigner,
  rerun,
  runQuery,
  settingsOf,
  setupReportClock,
} from '../../../test/reportScreen'
import { expectTab, showTab } from '../../../test/reportLayout'

setupReportClock()

const failWith = (...issues: ReportIssue[]): void =>
  mockControl.setReportQueryHandler(() => {
    throw invalidReport(issues)
  })

const issue = (location: (string | number)[], message: string, code = 'x'): ReportIssue => ({ location, code, message })

describe('정의 위반 표시', () => {
  // 테스트 코드: RQ-090
  it('정의 위반을 칩·설정·조건·결합·최대 행 옆에 표시하고 고칠 곳 목록을 보인다', async () => {
    // given: 컬럼 둘, 조건 하나가 있고 서버가 위반 다섯 개를 돌려준다
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, '금액')
    await addCondition(user, 'Deal 이름')
    await user.type(screen.getByRole('textbox', { name: '조건 1 값' }), '은행')
    failWith(
      issue(['columns', 0], '첫 컬럼 문구'),
      issue(['columns', 1, 'aggregate'], '집계 문구'),
      issue(['conditions', 0, 'value'], '조건 값 문구'),
      issue(['combine'], '결합 문구'),
      issue(['row_limit'], '최대 행 문구'),
    )

    // when: 조회한다
    await runQuery(user)

    // then: 고칠 곳 5개 요약에 위치와 문구가 모두 있다
    const summary = await screen.findByRole('alert')
    expect(summary).toHaveTextContent('고칠 곳 5개')
    expect(summary).toHaveTextContent('컬럼 1(Deal code)')
    expect(summary).toHaveTextContent('컬럼 2(금액)')
    expect(summary).toHaveTextContent('조건 1(Deal 이름)')
    expect(summary).toHaveTextContent('조건 결합')
    expect(summary).toHaveTextContent('최대 행')
    for (const message of ['첫 컬럼 문구', '집계 문구', '조건 값 문구', '결합 문구', '최대 행 문구']) {
      expect(summary).toHaveTextContent(message)
    }
    // then: 칩·집계 선택·조건 값·결합·최대 행에 오류 표시와 설명이 붙고 결과 표는 없다
    expect(chipItems()[0]).toHaveClass('is-invalid')
    expect(chipButton(0)).toHaveAccessibleDescription(/첫 컬럼 문구/)
    expect(chipItems()[1]).toHaveClass('is-invalid')
    const aggregate = within(settingsOf('금액')).getByRole('combobox', { name: '집계' })
    expect(aggregate).toHaveAttribute('aria-invalid', 'true')
    expect(aggregate).toHaveAccessibleDescription(/집계 문구/)
    const value = screen.getByRole('textbox', { name: '조건 1 값' })
    expect(value).toHaveAttribute('aria-invalid', 'true')
    expect(value).toHaveAccessibleDescription(/조건 값 문구/)
    expect(screen.getByRole('group', { name: '조건 결합' })).toHaveAccessibleDescription(/결합 문구/)
    expect(screen.getByRole('combobox', { name: '최대 행' })).toHaveAccessibleDescription(/최대 행 문구/)
    expect(screen.queryByRole('table', { name: '조회 결과' })).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-090
  it('컬럼 정렬 위반을 그 컬럼의 정렬 선택에 표시하고 정렬을 바꾸면 지운다', async () => {
    // given: Deal 이름을 내림차순 정렬했고 서버가 그 컬럼 정렬 위반을 돌려준다
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, 'Deal 이름')
    await user.selectOptions(within(settingsOf('Deal 이름')).getByRole('combobox', { name: '정렬' }), 'desc')
    failWith(issue(['columns', 1, 'sort'], '정렬 문구', 'sort-invalid'))

    // when: 조회한다
    await runQuery(user)

    // then: 요약에 컬럼 2와 문구가 있고 그 칩과 정렬 선택에만 오류 표시가 붙는다
    const summary = await screen.findByRole('alert')
    expect(summary).toHaveTextContent('컬럼 2(Deal 이름)')
    expect(summary).toHaveTextContent('정렬 문구')
    expect(chipItems()[1]).toHaveClass('is-invalid')
    expect(chipItems()[0]).not.toHaveClass('is-invalid')
    const select = within(settingsOf('Deal 이름')).getByRole('combobox', { name: '정렬' })
    expect(select).toHaveAttribute('aria-invalid', 'true')
    expect(select).toHaveAccessibleDescription(/정렬 문구/)

    // when: 정렬을 오름차순으로 바꾼다
    await user.selectOptions(select, 'asc')

    // then: 오류 표시와 문구가 사라진다
    expect(within(settingsOf('Deal 이름')).getByRole('combobox', { name: '정렬' })).not.toHaveAttribute('aria-invalid', 'true')
    expect(screen.queryByText('정렬 문구')).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-091
  it('예전 최상위 정렬 위치의 위반은 요약에만 보인다', async () => {
    // given: 서버가 최상위 sort 위치의 위반을 돌려준다
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    failWith(issue(['sort', 'column'], '예전 정렬 위치 문구'))

    // when: 조회한다
    await runQuery(user)

    // then: 요약에만 문구가 보이고 칩에는 오류 표시가 없다
    expect(await screen.findByRole('alert')).toHaveTextContent('예전 정렬 위치 문구')
    expect(chipItems()[0]).not.toHaveClass('is-invalid')
  })

  // 테스트 코드: RQ-091
  it('위치를 알 수 없는 위반은 요약에만 보인다', async () => {
    // given: 서버가 알 수 없는 위치의 위반을 돌려준다
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    failWith(issue(['nowhere'], '어디에도 없는 위치 문구'))

    // when: 조회한다
    await runQuery(user)

    // then: 요약에 고칠 곳 1개와 문구가 있고 칩에는 오류 표시가 없다
    const summary = await screen.findByRole('alert')
    expect(summary).toHaveTextContent('고칠 곳 1개')
    expect(summary).toHaveTextContent('어디에도 없는 위치 문구')
    expect(chipItems()[0]).not.toHaveClass('is-invalid')
  })

  // 테스트 코드: RQ-090
  it('서버가 돌려준 집계 필요 위반을 칩과 설정 옆에 표시한다', async () => {
    // given: Vendor, Deal code 컬럼이고 서버가 집계 필요 위반을 돌려준다
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, 'Deal code')
    failWith(issue(['columns', 1, 'aggregate'], '집계를 골라야 합니다 서버 문구', 'aggregate-required'))

    // when: 조회한다
    await runQuery(user)

    // then: 요약에 서버 문구가 있고 그 칩에 오류 표시가 붙는다
    const summary = await screen.findByRole('alert')
    expect(summary).toHaveTextContent('고칠 곳 1개')
    expect(summary).toHaveTextContent('집계를 골라야 합니다 서버 문구')
    expect(chipItems()[1]).toHaveClass('is-invalid')
  })

  // 테스트 코드: RQ-086
  it('그룹핑하면 텍스트 컬럼에 건수 집계를 채워 보내 집계 필요 위반 없이 조회된다', async () => {
    // given: Vendor, Deal code 컬럼
    const { user } = await openDesigner()
    await addColumn(user, 'Vendor')
    await addColumn(user, 'Deal code')
    // when: Vendor를 그룹핑하고 조회한다
    await user.click(chipButton(0))
    await user.click(within(settingsOf('Vendor')).getByRole('checkbox', { name: '그룹핑' }))

    await runQuery(user)

    // then: 결과 표가 보이고 위반 알림이 없으며 요청 Deal code 컬럼에 건수 집계가 있다
    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(lastQuery().columns).toEqual([
      { field: 'deal.vendor', group: true },
      { field: 'deal.code', group: false, aggregate: 'count' },
    ])
  })

  // 테스트 코드: RQ-090
  it('그룹핑 없이 Action 건수를 쓰면 서버 위반 문구를 칩에 표시한다', async () => {
    // given: Action 건수 컬럼만 있는 설계
    const { user } = await openDesigner()
    await addColumn(user, 'Action 건수')

    // when: 조회한다
    await runQuery(user)

    // then: 그룹핑할 때만 쓸 수 있다는 서버 문구가 보이고 그 칩에 오류 표시가 붙는다
    expect(await screen.findByRole('alert')).toHaveTextContent('이 컬럼은 그룹핑할 때만 쓸 수 있습니다. 그룹 컬럼을 추가하세요')
    expect(chipItems()[0]).toHaveClass('is-invalid')
  })
})

describe('위반 표시 해제', () => {
  // 테스트 코드: RQ-092
  it('고친 컬럼의 위반 표시는 사라지고 나머지는 남는다', async () => {
    // given: 컬럼 둘에 위반이 있고 고칠 곳 2개가 표시되어 있다
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, 'Deal 이름')
    failWith(issue(['columns', 0], '코드 컬럼 문구'), issue(['columns', 1, 'label'], '이름 컬럼 문구'))
    await runQuery(user)
    expect(await screen.findByRole('alert')).toHaveTextContent('고칠 곳 2개')

    // when: Deal 이름 컬럼의 표시 이름을 고친다
    await user.type(within(settingsOf('Deal 이름')).getByRole('textbox', { name: '표시 이름' }), '이름')

    // then: 고칠 곳 1개만 남고 고친 칩의 오류 표시가 사라진다
    const summary = screen.getByRole('alert')
    expect(summary).toHaveTextContent('고칠 곳 1개')
    expect(summary).toHaveTextContent('코드 컬럼 문구')
    expect(summary).not.toHaveTextContent('이름 컬럼 문구')
    expect(chipItems()[1]).not.toHaveClass('is-invalid')
    expect(chipItems()[0]).toHaveClass('is-invalid')
  })

  // 테스트 코드: RQ-092
  it('지운 컬럼의 위반은 없어지고 더 남지 않으면 요약도 사라진다', async () => {
    // given: 컬럼 둘이고 둘째 컬럼에 위반이 표시되어 있다
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, 'Deal 이름')
    failWith(issue(['columns', 1, 'field'], '이름 컬럼 문구'))
    await runQuery(user)
    await screen.findByRole('alert')

    // when: 둘째 컬럼을 뺀다
    await user.click(screen.getByRole('button', { name: 'Deal 이름 빼기' }))

    // then: 요약이 사라지고 칩은 하나다
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(chipItems()).toHaveLength(1)
  })

  // 테스트 코드: RQ-092
  it('값을 고친 조건의 위반 표시는 사라진다', async () => {
    // given: 조건 값에 위반이 표시되어 있다
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, 'Deal 이름')
    await user.type(screen.getByRole('textbox', { name: '조건 1 값' }), '은행')
    failWith(issue(['conditions', 0, 'value'], '조건 값 문구'))
    await runQuery(user)
    await screen.findByRole('alert')

    // when: 조건 값을 고친다
    await user.type(screen.getByRole('textbox', { name: '조건 1 값' }), '권')

    // then: 요약이 사라지고 값 칸의 오류 표시도 없다
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: '조건 1 값' })).not.toHaveAttribute('aria-invalid', 'true')
  })
})

describe('그 밖의 실패', () => {
  // 테스트 코드: RQ-093
  it('시간 초과·연결 끊김은 작성 탭에 서버 문구로 보이고 결과 탭에는 이전 결과가 남는다', async () => {
    // given: 한 번 조회한 결과가 있다
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await runQuery(user)
    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()

    // when: 시간 초과를 내는 서버로 다시 조회한다
    mockControl.setReportQueryHandler(() => {
      throw reportTimeout()
    })
    await rerun(user)

    // then: 시간 초과 문구가 작성 탭에 보이고 결과 탭에는 이전 결과가 남는다
    expect(await screen.findByRole('alert')).toHaveTextContent(REPORT_TIMEOUT_MESSAGE)
    expectTab('design')

    // when: 결과 탭으로 옮긴다
    await showTab(user, 'result')
    // then: 이전 결과 표가 남아 있다
    expect(screen.getByRole('table', { name: '조회 결과' })).toBeVisible()

    // when: 작성 탭으로 돌아온다
    await showTab(user, 'design')

    // when: 연결이 끊긴 서버로 다시 조회한다
    mockControl.setReportQueryHandler(() => {
      throw new ApiError(0, { type: 'https://x/problems/network', title: 'Network Error', status: 0, detail: '서버에 연결할 수 없습니다.' })
    })
    await runQuery(user)

    // then: 연결 끊김 문구가 보이고 시간 초과 문구는 없다
    expect(await screen.findByRole('alert')).toHaveTextContent('서버에 연결할 수 없습니다.')
    expect(screen.getByRole('alert')).not.toHaveTextContent(REPORT_TIMEOUT_MESSAGE)
    expectTab('design')
  })

  // 테스트 코드: RQ-093
  it('그 밖의 서버 오류는 서버 문구를 보인다', async () => {
    // given: 500 오류를 내는 서버
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    mockControl.setReportQueryHandler(() => {
      throw new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '서버 내부 오류입니다' })
    })

    // when: 조회한다
    await runQuery(user)

    // then: 서버 오류 문구가 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('서버 내부 오류입니다')
  })

  // 테스트 코드: RQ-092
  it('조회가 성공하면 실패 알림이 사라진다', async () => {
    // given: 시간 초과로 실패 알림이 보인다
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    mockControl.setReportQueryHandler(() => {
      throw reportTimeout()
    })
    await runQuery(user)
    await screen.findByRole('alert')

    // when: 서버가 정상으로 돌아와 다시 조회한다
    mockControl.setReportQueryHandler(null)
    await runQuery(user)

    // then: 결과 표가 보이고 알림이 없다
    expect(await screen.findByRole('table', { name: '조회 결과' })).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
