import { useState, useRef, useCallback, KeyboardEvent } from 'react'
import { X } from 'lucide-react'
import { ICON_SIZE } from '../theme'
import type { SearchValue } from '../types'
import styles from './SearchBar.module.css'

export interface SearchBarProps {
  value: SearchValue
  onChange: (v: SearchValue) => void
  onSubmit?: () => void
  availableTags: string[]
  placeholder?: string
  id?: string
}

function normalizeTag(raw: string): string {
  return raw.trim().toLowerCase()
}

export function SearchBar({
  value,
  onChange,
  onSubmit,
  availableTags,
  placeholder = 'Search...',
  id,
}: SearchBarProps) {
  const [inputText, setInputText] = useState(() => value.text)
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)

  const promoteTag = useCallback(
    (raw: string) => {
      const normalized = normalizeTag(raw)
      if (!normalized) return
      if (value.tags.includes(normalized)) return
      onChange({ tags: [...value.tags, normalized], text: '' })
      setInputText('')
      setDropdownOpen(false)
      setActiveIndex(-1)
    },
    [value, onChange]
  )

  const removeTag = useCallback(
    (tag: string) => {
      onChange({ ...value, tags: value.tags.filter((t) => t !== tag) })
    },
    [value, onChange]
  )

  const lowerInput = inputText.trim().toLowerCase()

  const matchingSuggestions = lowerInput
    ? availableTags.filter(
        (t) => t.toLowerCase().includes(lowerInput) && !value.tags.includes(t.toLowerCase())
      )
    : []

  const showDropdown = dropdownOpen && matchingSuggestions.length > 0

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && inputText === '' && value.tags.length > 0) {
      onChange({ ...value, tags: value.tags.slice(0, -1) })
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (!showDropdown && lowerInput) setDropdownOpen(true)
      setActiveIndex((i) => Math.min(i + 1, matchingSuggestions.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, -1))
    } else if (e.key === 'Tab') {
      if (showDropdown && matchingSuggestions.length > 0) {
        e.preventDefault()
        promoteTag(activeIndex >= 0 ? matchingSuggestions[activeIndex] : matchingSuggestions[0])
      }
    } else if (e.key === 'Enter') {
      e.preventDefault()
      onSubmit?.()
    } else if (e.key === 'Escape') {
      setDropdownOpen(false)
      setActiveIndex(-1)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setInputText(val)
    onChange({ ...value, text: val })
    setDropdownOpen(val.trim().length > 0)
    setActiveIndex(-1)
  }

  const handleBlur = () => {
    setDropdownOpen(false)
    setActiveIndex(-1)
  }

  const handleDropdownMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
  }

  return (
    <div className={styles.container}>
      <div className={styles.inputRow}>
        {value.tags.map((tag) => (
          <span key={tag} className={styles.chip}>
            <span className={styles.chipLabel}>{tag}</span>
            <button
              type="button"
              className={styles.chipRemove}
              aria-label={`Remove ${tag}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => removeTag(tag)}
            >
              <X size={ICON_SIZE.xs} />
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          id={id}
          type="text"
          className={styles.input}
          value={inputText}
          placeholder={value.tags.length === 0 ? placeholder : ''}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
          autoComplete="off"
          aria-autocomplete="list"
          aria-expanded={showDropdown}
        />
      </div>

      {showDropdown && (
        <ul
          role="listbox"
          className={styles.dropdown}
          onMouseDown={handleDropdownMouseDown}
        >
          {matchingSuggestions.map((tag, idx) => (
            <li
              key={tag}
              role="option"
              aria-selected={activeIndex === idx}
              className={
                activeIndex === idx
                  ? `${styles.dropdownItem} ${styles.dropdownItemActive}`
                  : styles.dropdownItem
              }
              onClick={() => {
                promoteTag(tag)
                inputRef.current?.focus()
              }}
            >
              {tag}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
