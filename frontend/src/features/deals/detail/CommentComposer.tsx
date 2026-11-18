import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useCommentWriting, useCreateComment } from '../../../data/comments'
import { messageOf } from './detailHelpers'

interface CommentComposerProps {
  dealCode: string
  /** 있으면 그 Action의 Comment, 없으면 Deal Comment. */
  actionId?: number
  /** 열릴 때 입력 칸에 포커스를 둔다(Actions 표의 Comment 아이콘으로 열었을 때). */
  focusOnOpen?: boolean
}

/** Comment 입력 칸(저장 버튼 없음). Enter로 저장하고 Shift+Enter는 줄을 바꾼다. 빈 글은 화면에서 막고, 서버 문구는 그대로 보인다. */
export function CommentComposer({ dealCode, actionId, focusOnOpen = false }: CommentComposerProps) {
  const create = useCreateComment()
  const [body, setBody] = useState('')
  const [error, setError] = useState<string | null>(null)
  const boxRef = useRef<HTMLTextAreaElement>(null)
  const writing = useCommentWriting()
  const refocus = useRef(false)

  // 저장 중에는 입력 칸이 꺼져 포커스를 둘 수 없으므로, 다시 켜진 뒤에 포커스를 돌려준다.
  useEffect(() => {
    if (!writing && refocus.current) {
      refocus.current = false
      boxRef.current?.focus()
    }
  }, [writing])

  async function save() {
    if (create.isPending) return
    if (body.trim() === '') {
      setError('Comment를 입력하세요.')
      return
    }
    setError(null)
    try {
      await create.mutateAsync({ dealCode, body, ...(actionId === undefined ? {} : { actionId }) })
      setBody('')
      refocus.current = true
      boxRef.current?.focus()
    } catch (caught) {
      setError(messageOf(caught))
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return
    event.preventDefault()
    void save()
  }

  return (
    <div className="cm-composer">
      <label className="field">
        <span>Comment 입력</span>
        <textarea
          ref={boxRef}
          rows={3}
          placeholder="Comment를 입력하세요"
          disabled={writing}
          value={body}
          data-autofocus={focusOnOpen ? '' : undefined}
          aria-invalid={error ? true : undefined}
          onChange={(e) => {
            setBody(e.target.value)
            setError(null)
          }}
          onKeyDown={onKeyDown}
        />
      </label>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <span className="hint">Enter로 저장, Shift+Enter로 줄 바꿈</span>
    </div>
  )
}
