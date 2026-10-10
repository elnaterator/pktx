import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { ChevronDown } from 'lucide-react'
import type { Assistant } from './connectAssistants'
import { AssistantIcon } from './AssistantIcon'
import styles from './Connect.module.css'

interface AssistantPickerProps {
  assistants: Assistant[]
  value: string
  onChange: (id: string) => void
  label: string
}

/**
 * Select-only combobox (WAI-ARIA listbox pattern). A native `<select>` can't
 * render icons, so this rebuilds its keyboard model: ↑/↓/Home/End move,
 * Enter/Space pick, Esc/Tab close, typing a letter jumps to the next match.
 */
export function AssistantPicker({ assistants, value, onChange, label }: AssistantPickerProps) {
  const id = useId()
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const listRef = useRef<HTMLUListElement>(null)

  const selectedIndex = Math.max(
    0,
    assistants.findIndex((a) => a.id === value),
  )
  const selected = assistants[selectedIndex]
  const optionId = (i: number) => `${id}-opt-${i}`

  useEffect(() => {
    if (!open) return
    listRef.current?.focus()
    const onPointerDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open])

  useEffect(() => {
    if (open) document.getElementById(`${id}-opt-${active}`)?.scrollIntoView?.({ block: 'nearest' })
  }, [id, open, active])

  const openList = (index = selectedIndex) => {
    setActive(index)
    setOpen(true)
  }

  const close = (refocus = true) => {
    setOpen(false)
    if (refocus) buttonRef.current?.focus()
  }

  const pick = (index: number) => {
    onChange(assistants[index].id)
    close()
  }

  const onButtonKeyDown = (e: KeyboardEvent) => {
    if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
      e.preventDefault()
      openList()
    }
  }

  const onListKeyDown = (e: KeyboardEvent) => {
    const last = assistants.length - 1
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setActive((i) => Math.min(last, i + 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setActive((i) => Math.max(0, i - 1))
        break
      case 'Home':
        e.preventDefault()
        setActive(0)
        break
      case 'End':
        e.preventDefault()
        setActive(last)
        break
      case 'Enter':
      case ' ':
        e.preventDefault()
        pick(active)
        break
      case 'Escape':
        e.preventDefault()
        close()
        break
      case 'Tab':
        close(false)
        break
      default:
        if (e.key.length === 1 && /\S/.test(e.key)) {
          const key = e.key.toLowerCase()
          const order = [...assistants.keys()].map((n) => (active + 1 + n) % assistants.length)
          const match = order.find((i) => assistants[i].name.toLowerCase().startsWith(key))
          if (match !== undefined) setActive(match)
        }
    }
  }

  return (
    <div className={styles.picker} ref={rootRef}>
      <span className={styles.pickerLabel} id={`${id}-label`}>
        {label}
      </span>
      <button
        ref={buttonRef}
        type="button"
        className={styles.pickerButton}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={`${id}-list`}
        aria-labelledby={`${id}-label ${id}-value`}
        onClick={() => (open ? close() : openList())}
        onKeyDown={onButtonKeyDown}
      >
        <span className={styles.pickerIcon}>
          <AssistantIcon id={selected.id} />
        </span>
        <span className={styles.pickerName} id={`${id}-value`}>
          {selected.name}
        </span>
        <ChevronDown
          size={16}
          aria-hidden="true"
          className={`${styles.pickerChevron} ${open ? styles.pickerChevronOpen : ''}`}
        />
      </button>
      {open && (
        <ul
          ref={listRef}
          id={`${id}-list`}
          role="listbox"
          tabIndex={-1}
          aria-labelledby={`${id}-label`}
          aria-activedescendant={optionId(active)}
          className={styles.pickerList}
          onKeyDown={onListKeyDown}
        >
          {assistants.map((a, i) => (
            <li
              key={a.id}
              id={optionId(i)}
              role="option"
              aria-selected={i === selectedIndex}
              className={`${styles.pickerOption} ${i === active ? styles.pickerOptionActive : ''}`}
              onPointerMove={() => setActive(i)}
              onClick={() => pick(i)}
            >
              <span className={styles.pickerIcon}>
                <AssistantIcon id={a.id} />
              </span>
              <span className={styles.pickerName}>{a.name}</span>
              <span className={styles.pickerNoun}>{a.noun}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
