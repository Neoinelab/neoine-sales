import { describe, expect, it } from 'vitest'
import { USER_ID } from '../../test/fake/seed/ids'
import { canDeleteDeal, dealDeleteDenial } from './permissions'
import type { Viewer } from './permissions'

const OWNER_DENIED = '본인 Deal 또는 admin만 삭제할 수 있습니다.'
const COMPLETED_DENIED = '완료된 Deal은 관리자만 삭제할 수 있습니다.'

const root: Viewer = { id: USER_ID.root, role: 'admin' }
const kim: Viewer = { id: USER_ID.kim, role: 'sales' }
const han: Viewer = { id: USER_ID.han, role: 'user' }

describe('dealDeleteDenial (완료된 Deal 삭제 판정)', () => {
  // 삭제 판정은 완료된 Deal을 admin에게만 허용하고 거절 문구를 서버 순서대로 고른다.
  // 테스트 코드: DD-124
  it.each([
    ['admin은 남의 Won Deal을 지울 수 있다', root, USER_ID.kim, 'won', null],
    ['Owner 영업은 자기 Won Deal에서 완료 문구로 거절된다', kim, USER_ID.kim, 'won', COMPLETED_DENIED],
    ['Owner 영업은 자기 Lost Deal을 지울 수 있다', kim, USER_ID.kim, 'lost', null],
    ['다른 영업은 남의 Won Deal에서 Owner 문구로 거절된다(Owner 판정이 먼저)', kim, USER_ID.park, 'won', OWNER_DENIED],
  ] as const)('%s', (_name, viewer, ownerId, forecastKey, expected) => {
    // when: 삭제 판정 함수를 부른다
    const denial = dealDeleteDenial(viewer, ownerId, forecastKey)

    // then: 허용이면 null, 거절이면 서버와 같은 문구다
    expect(denial).toBe(expected)
    expect(canDeleteDeal(viewer, ownerId, forecastKey)).toBe(expected === null)
  })

  // user는 Owner id가 같아도 완료된 Deal을 지울 수 없다.
  // 테스트 코드: DD-124
  it('거절한다: user는 Owner id가 같은 Won Deal도 지울 수 없다', () => {
    // when: user가 Owner id가 같은 Won Deal의 삭제를 판정한다
    const denial = dealDeleteDenial(han, USER_ID.han, 'won')

    // then: 거절 문구가 있고 삭제할 수 없다
    expect(denial).not.toBeNull()
    expect(canDeleteDeal(han, USER_ID.han, 'won')).toBe(false)
  })

  // Won이 아닌 모든 Forecast key는 완료로 보지 않는다.
  it.each(['pipeline', 'best', 'most_likely', 'commit', 'lost'])('Owner 영업은 Forecast %s Deal을 지울 수 있다', (forecastKey) => {
    // when: Owner 영업이 Won이 아닌 Deal의 삭제를 판정한다
    const denial = dealDeleteDenial(kim, USER_ID.kim, forecastKey)

    // then: 허용(null)이다
    expect(denial).toBeNull()
  })

  // 완료 판정은 코드 이름이 아니라 key(won)로 한다.
  it('완료 판정은 key로 하므로 won이 아닌 비슷한 key는 완료가 아니다', () => {
    // when: key가 'Won'(대문자)·'won_x'인 Deal을 판정한다
    const upper = dealDeleteDenial(kim, USER_ID.kim, 'Won')
    const similar = dealDeleteDenial(kim, USER_ID.kim, 'won_x')

    // then: 둘 다 허용이다
    expect(upper).toBeNull()
    expect(similar).toBeNull()
  })
})
