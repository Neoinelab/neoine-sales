import { describe, expect, it } from 'vitest'
import { toContactBody } from './contact'

describe('toContactBody', () => {
  it('sends an empty title as null and keeps the other fields', () => {
    expect(toContactBody({ company: 'A', name: 'B', title: '', email: 'a@b.co', phone: null })).toEqual({
      company: 'A',
      name: 'B',
      title: null,
      email: 'a@b.co',
      phone: null,
    })
  })

  it('keeps a title as typed', () => {
    expect(toContactBody({ company: 'A', name: 'B', title: '팀 장', email: null, phone: null }).title).toBe('팀 장')
  })
})
