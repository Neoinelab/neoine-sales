import { api } from '../../shared/api/client'
import type { TimeGateway } from '../types'
import { malformedResponse, unwrap } from './request'

const WITH_OFFSET = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/

export function createTimeHttp(): TimeGateway {
  return {
    get: async () => {
      const body = await unwrap(api.GET('/api/v1/time'))
      if (!WITH_OFFSET.test(body.now) || Number.isNaN(Date.parse(body.now)) || !DATE_ONLY.test(body.today)) throw malformedResponse()
      return { now: body.now, today: body.today }
    },
  }
}
