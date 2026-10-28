import { useRef, useEffect } from 'react'

interface AutoResizeTextareaProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
  id?: string
  'aria-label'?: string
  'data-bullet'?: boolean
  onKeyDown?: React.KeyboardEventHandler<HTMLTextAreaElement>
}

export function AutoResizeTextarea({
  value,
  onChange,
  placeholder,
  className,
  id,
  'aria-label': ariaLabel,
  'data-bullet': dataBullet,
  onKeyDown,
}: AutoResizeTextareaProps) {
  const ref = useRef<HTMLTextAreaElement>(null)
  const isManuallyResized = useRef(false)

  const autoResize = (el: HTMLTextAreaElement | null) => {
    if (!el || isManuallyResized.current) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }

  useEffect(() => { autoResize(ref.current) }, [value])

  useEffect(() => {
    const el = ref.current
    if (!el) return

    let heightBeforeMousedown = 0

    const onMousedown = () => { heightBeforeMousedown = el.offsetHeight }
    const onMouseup = () => {
      if (el.offsetHeight !== heightBeforeMousedown) {
        isManuallyResized.current = true
      }
    }

    el.addEventListener('mousedown', onMousedown)
    document.addEventListener('mouseup', onMouseup)
    return () => {
      el.removeEventListener('mousedown', onMousedown)
      document.removeEventListener('mouseup', onMouseup)
    }
  }, [])

  return (
    <textarea
      ref={(el) => {
        (ref as React.MutableRefObject<HTMLTextAreaElement | null>).current = el
        autoResize(el)
      }}
      id={id}
      aria-label={ariaLabel}
      data-bullet={dataBullet || undefined}
      className={className}
      placeholder={placeholder}
      value={value}
      rows={1}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={onKeyDown}
      style={{ resize: 'vertical', overflow: 'auto' }}
    />
  )
}
