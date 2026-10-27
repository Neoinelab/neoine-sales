import { describe, expect, it } from 'vitest'
import type { ReportIssue } from '../../../../shared/model/reportTypes'
import { issueAnchors, visibleIssues } from './issues'

const RUN = { columnUids: [10, 11, 12], conditionUids: [20, 21] }

const issue = (location: (string | number)[], message = '문구'): ReportIssue => ({ location, code: 'x', message })

describe('issueAnchors (AC13)', () => {
  it('maps server locations to column and condition uids of the last run', () => {
    const issues = [
      issue(['columns', 1, 'field']),
      issue(['columns', 2]),
      issue(['columns']),
      issue(['conditions', 0, 'value']),
      issue(['conditions', 1]),
      issue(['conditions']),
      issue(['combine']),
      issue(['sort', 'column']),
      issue(['sort']),
      issue(['row_limit']),
    ]

    const anchored = issueAnchors(issues, RUN)

    expect(anchored.map((a) => a.target)).toEqual([
      { kind: 'column', uid: 11, part: 'field' },
      { kind: 'column', uid: 12, part: null },
      { kind: 'columns' },
      { kind: 'condition', uid: 20, part: 'value' },
      { kind: 'condition', uid: 21, part: null },
      { kind: 'conditions' },
      { kind: 'combine' },
      { kind: 'sort' },
      { kind: 'sort' },
      { kind: 'rowLimit' },
    ])
    expect(anchored.map((a) => a.issue)).toEqual(issues)
  })

  it('puts a location it does not know in the general list', () => {
    const anchored = issueAnchors([issue(['nowhere']), issue(['columns', 9, 'field']), issue([])], RUN)

    expect(anchored.map((a) => a.target)).toEqual([{ kind: 'general' }, { kind: 'general' }, { kind: 'general' }])
  })
})

describe('visibleIssues (AC13)', () => {
  const anchored = issueAnchors(
    [issue(['columns', 0, 'aggregate'], 'a'), issue(['columns', 1, 'field'], 'b'), issue(['conditions', 0, 'value'], 'c'), issue(['row_limit'], 'd'), issue(['x'], 'e')],
    RUN,
  )
  const live = { columnUids: [10, 11, 12], conditionUids: [20, 21] }

  it('keeps everything while nothing changed', () => {
    expect(visibleIssues(anchored, live, new Set()).map((a) => a.issue.message)).toEqual(['a', 'b', 'c', 'd', 'e'])
  })

  it('drops issues of removed or edited items', () => {
    const afterRemove = { columnUids: [11, 12], conditionUids: [21] }

    const visible = visibleIssues(anchored, afterRemove, new Set([11]))

    expect(visible.map((a) => a.issue.message)).toEqual(['d', 'e'])
  })

  it('drops the issues of an edited item only', () => {
    const visible = visibleIssues(anchored, live, new Set([10]))

    expect(visible.map((a) => a.issue.message)).toEqual(['b', 'c', 'd', 'e'])
  })
})
