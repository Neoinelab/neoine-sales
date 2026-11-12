/** Fake 게이트웨이의 선택 목록(Label·유형·Vendor) 규칙이 서버와 같은지 확인한다(서버 문구·판정 순서·정렬). */

import { describe, expect, it } from 'vitest'
import { seedVendorId } from '../../fixtures/vendors'
import { NO_SUCH_ID } from '../seed/ids'
import { expectApiError, mockAs } from '../testing'

describe('BANT Label Fake는 서버 규칙을 따른다', () => {
  // NUL 문자가 든 이름은 등록과 이름 변경 모두 서버 문구로 거절한다.
  it('NUL이 든 이름은 등록·이름 변경 모두 NUL 문구의 422다', async () => {
    // given: admin과 기본 Label 하나
    const { gateway } = await mockAs('root')
    const first = (await gateway.labels.list())[0]
    if (!first) throw new Error('시드 Label이 없습니다.')

    // when·then: NUL이 든 이름으로 만들고, 같은 이름으로 바꾼다 → 둘 다 422 NUL 문구이고 Label은 그대로다
    await expectApiError(gateway.labels.create('need', 'a\u0000b'), 422, 'Label 이름에는 NUL 문자를 쓸 수 없습니다')
    await expectApiError(gateway.labels.rename(first.id, '\u0000'), 422, 'Label 이름에는 NUL 문자를 쓸 수 없습니다')
    expect((await gateway.labels.list())[0]?.name).toBe(first.name)
  })

  // 없는 id여도 잘못된 이름이면 이름 오류(422)가 먼저 나온다.
  it('잘못된 새 이름은 없는 id여도 404보다 먼저 422다', async () => {
    // given: admin
    const { gateway } = await mockAs('root')

    // when·then: 없는 id를 공백뿐인 이름으로 바꾼다 → 404가 아니라 필수 문구 422다
    await expectApiError(gateway.labels.rename(NO_SUCH_ID, '   '), 422, 'Label 이름을 입력하세요.')
  })

  // 없는 Label의 이름 변경·삭제는 서버와 같은 찾을 수 없음 문구의 404다.
  it('없는 Label은 서버 문구의 404다', async () => {
    // given: admin
    const { gateway } = await mockAs('root')

    // when: 없는 id의 이름을 바꾸고, 삭제한다
    const message = `BANT Label을(를) 찾을 수 없습니다: ${NO_SUCH_ID}`
    // then: 둘 다 404 'BANT Label을(를) 찾을 수 없습니다: <id>'다
    await expectApiError(gateway.labels.rename(NO_SUCH_ID, '아무거나'), 404, message)
    await expectApiError(gateway.labels.remove(NO_SUCH_ID), 404, message)
  })

  // 직접 만든 Label은 기본 Label 뒤에 소문자 이름의 코드 포인트 순으로 나온다.
  it('직접 만든 Label은 소문자 코드 포인트 순이다', async () => {
    // given: need 구분에 '나중에', 'Zeta', 'alpha'를 차례로 만들었다
    const { gateway } = await mockAs('kim')
    for (const name of ['나중에', 'Zeta', 'alpha']) await gateway.labels.create('need', name)

    // when: 목록을 읽는다
    const need = (await gateway.labels.list()).filter((l) => l.category === 'need')

    // then: 기본 Label 뒤에 alpha, Zeta, 나중에 순이다
    expect(need.slice(-3).map((l) => l.name)).toEqual(['alpha', 'Zeta', '나중에'])
    expect(need.slice(0, -3).every((l) => l.isDefault)).toBe(true)
  })

  // 모르는 구분은 서버의 요청 형식 오류(422)와 같은 문구로 거절한다.
  it('모르는 구분은 요청 형식 오류의 422다', async () => {
    // given: sales
    const { gateway } = await mockAs('kim')

    // when·then: 모르는 구분으로 만든다 → 422 '요청 형식이 올바르지 않습니다'다
    await expectApiError(gateway.labels.create('money' as never, 'x'), 422, '요청 형식이 올바르지 않습니다')
  })
})

describe('Action 유형 Fake는 서버 규칙을 따른다', () => {
  // NUL 문자가 든 유형 이름은 서버 문구로 거절한다.
  it('NUL이 든 유형 이름은 NUL 문구의 422다', async () => {
    // given: sales
    const { gateway } = await mockAs('kim')

    // when·then: NUL이 든 이름으로 만든다 → 422 '유형에는 NUL 문자를 쓸 수 없습니다'다
    await expectApiError(gateway.actionTypes.create('웨\u0000비나'), 422, '유형에는 NUL 문자를 쓸 수 없습니다')
  })

  // 없는 유형의 이름 변경·삭제는 서버와 같은 문구의 404다.
  it('없는 유형은 서버 문구의 404다', async () => {
    // given: admin
    const { gateway } = await mockAs('root')

    // when: 없는 id의 이름을 바꾸고, 삭제한다
    const message = `Action 유형을(를) 찾을 수 없습니다: ${NO_SUCH_ID}`
    // then: 둘 다 404 'Action 유형을(를) 찾을 수 없습니다: <id>'다
    await expectApiError(gateway.actionTypes.rename(NO_SUCH_ID, '무엇'), 404, message)
    await expectApiError(gateway.actionTypes.remove(NO_SUCH_ID), 404, message)
    expect(await gateway.actionTypes.list()).toHaveLength(8)
  })
})

describe('Vendor Fake는 서버 규칙을 따른다', () => {
  // NUL 문자가 든 Vendor 이름은 서버 문구로 거절한다.
  it('NUL이 든 Vendor 이름은 NUL 문구의 422다', async () => {
    // given: admin
    const { gateway } = await mockAs('root')

    // when·then: NUL이 든 이름으로 만든다 → 422 'Vendor 이름에는 NUL 문자를 쓸 수 없습니다'다
    await expectApiError(gateway.vendors.create('a\u0000b'), 422, 'Vendor 이름에는 NUL 문자를 쓸 수 없습니다')
  })

  // 없는 id여도 잘못된 이름이면 이름 오류(422)가 먼저 나온다.
  it('잘못된 새 이름은 없는 id여도 404보다 먼저 422다', async () => {
    // given: admin
    const { gateway } = await mockAs('root')

    // when·then: 없는 Vendor를 공백뿐인 이름으로 바꾼다 → 404가 아니라 필수 문구 422다
    await expectApiError(gateway.vendors.rename(NO_SUCH_ID, '   '), 422, 'Vendor 이름을 입력하세요.')
  })

  // 없는 Vendor의 이름 변경·삭제는 서버와 같은 문구의 404다.
  it('없는 Vendor는 서버 문구의 404다', async () => {
    // given: admin
    const { gateway } = await mockAs('root')

    // when: 없는 id의 이름을 바꾸고, 삭제한다
    const message = `Vendor을(를) 찾을 수 없습니다: ${NO_SUCH_ID}`
    // then: 둘 다 404 'Vendor을(를) 찾을 수 없습니다: <id>'다
    await expectApiError(gateway.vendors.rename(NO_SUCH_ID, 'X'), 404, message)
    await expectApiError(gateway.vendors.remove(NO_SUCH_ID), 404, message)
    expect((await gateway.vendors.list()).some((v) => v.id === seedVendorId('Okta'))).toBe(true)
  })
})
