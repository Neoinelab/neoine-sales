/** 계약 스위트를 mock 구현에 대해 실행한다(기본 실행). 같은 스위트를 실제 서버에 돌리는 것은 보고서의 test:live 항목 참고. */

import { beforeEach } from 'vitest'
import { newMock } from '../../test/fake/testing'
import type { MockInstance } from '../../test/fake'
import { alertsContract } from './alerts.contract'
import { actionsContract } from './actions.contract'
import { actionsSequenceContract } from './actionsSequence.contract'
import { actionsStatusContract } from './actionsStatus.contract'
import { actionTypesContract } from './actionTypes.contract'
import { dealBantContract } from './dealBant.contract'
import { attachmentsContract } from './attachments.contract'
import { codesContract } from './codes.contract'
import { contactsContract } from './contacts.contract'
import { dealsContract } from './deals.contract'
import { labelsContract } from './labels.contract'
import { vendorsContract } from './vendors.contract'
import type { MakeGateway } from './support'

const ROLE_USER_ID = { admin: 'u-root', sales: 'u-kim', user: 'u-han' } as const

// 테스트마다 새 mock 하나. 같은 테스트 안의 make 호출은 그 mock을 공유하고 마지막으로 만든 역할로 로그인된다.
let current: MockInstance
beforeEach(() => {
  current = newMock()
})

const makeMock: MakeGateway = async (role) => {
  await current.gateway.auth.quickLogin(ROLE_USER_ID[role])
  return current.gateway
}

codesContract(makeMock)
labelsContract(makeMock)
vendorsContract(makeMock)
contactsContract(makeMock)
dealsContract(makeMock)
actionsContract(makeMock)
actionsSequenceContract(makeMock)
actionsStatusContract(makeMock)
actionTypesContract(makeMock)
dealBantContract(makeMock)
attachmentsContract(makeMock)
alertsContract(makeMock)
