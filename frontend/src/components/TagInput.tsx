import { useState, useRef, useCallback, KeyboardEvent } from 'react'
import { X } from 'lucide-react'
import { ICON_SIZE } from '../theme'
import styles from './TagInput.module.css'

export interface TagInputProps {
  value: string[]
  onChange: (tags: string[]) => void
  availableTags: string[]
  allowCreate?: boolean
  placeholder?: string
  id?: string
}

function normalizeTag(raw: string): string {
  return raw.trim().toLowerCase()
}

/** Separators accepted when pasting multiple values at once. */
const PASTE_SPLIT = /[,;\n\r\t]+/

export function TagInput({
  value,
  onChange,
  availableTags,
  allowCreate = true,
  placeholder = 'Add tag...',
  id,
}: TagInputProps) {
  const [inputText, setInputText] = useState('')
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)

  // Folds every value into one onChange so a multi-value paste can't drop
  // entries to stale-closure reads of `value`.
  const commitTags = useCallback(
    (raws: string[]) => {
      const next = [...value]
      for (const raw of raws) {
        const normalized = normalizeTag(raw)
        if (!normalized) continue
        if (next.some((v) => v.toLowerCase() === normalized.toLowerCase())) continue
        next.push(normalized)
      }
      if (next.length !== value.length) onChange(next)
      setInputText('')
      setDropdownOpen(false)
      setActiveIndex(-1)
    },
    [value, onChange]
  )

  const commitTag = useCallback((raw: string) => commitTags([raw]), [commitTags])

  const removeTag = useCallback(
    (tag: string) => {
      onChange(value.filter((t) => t !== tag))
    },
    [value, onChange]
  )

  const lowerInput = inputText.trim().toLowerCase()

  const matchingSuggestions = lowerInput
    ? availableTags.filter(
        (t) =>
          t.toLowerCase().includes(lowerInput) &&
          !value.some((v) => v.toLowerCase() === t.toLowerCase())
      )
    : []

  // Flat list of committable items in dropdown order
  const dropdownItems: string[] = [
    ...matchingSuggestions,
    ...(allowCreate && lowerInput ? [inputText] : []),
  ]

  const showDropdown = dropdownOpen && lowerInput.length > 0

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && inputText === '' && value.length > 0) {
      onChange(value.slice(0, -1))
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (!showDropdown && lowerInput) setDropdownOpen(true)
      setActiveIndex((i) => Math.min(i + 1, dropdownItems.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, -1))
    } else if (e.key === 'Tab') {
      if (showDropdown && dropdownItems.length > 0) {
        e.preventDefault()
        commitTag(activeIndex >= 0 ? dropdownItems[activeIndex] : dropdownItems[0])
      }
      // else: tab moves focus naturally; blur fires and commits typed text
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (activeIndex >= 0 && dropdownItems[activeIndex] !== undefined) {
        commitTag(dropdownItems[activeIndex])
      } else {
        commitTag(inputText)
      }
    } else if (e.key === ',') {
      e.preventDefault()
      commitTag(inputText)
    } else if (e.key === 'Escape') {
      setDropdownOpen(false)
      setActiveIndex(-1)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setInputText(val)
    setDropdownOpen(val.trim().length > 0)
    setActiveIndex(-1)
  }

  // Pasting a separated list ("Python, Go; Rust") commits every value at once.
  // A paste with no separator falls through to the browser default.
  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const pasted = e.clipboardData.getData('text')
    if (!PASTE_SPLIT.test(pasted)) return
    e.preventDefault()
    commitTags((inputText + pasted).split(PASTE_SPLIT))
  }

  const handleBlur = () => {
    if (inputText.trim()) {
      commitTag(inputText)
    }
    setDropdownOpen(false)
    setActiveIndex(-1)
  }

  const handleDropdownMouseDown = (e: React.MouseEvent) => {
    // Prevent input from losing focus so blur never fires during a dropdown click
    e.preventDefault()
  }

  // Index of the "create" option within dropdownItems (last item, if present)
  const createIndex = allowCreate && lowerInput ? dropdownItems.length - 1 : -1

  return (
    <div className={styles.container}>
      <div className={styles.inputRow}>
        {value.map((tag) => (
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
          placeholder={value.length === 0 ? placeholder : ''}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
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
                commitTag(tag)
                inputRef.current?.focus()
              }}
            >
              {tag}
            </li>
          ))}
          {allowCreate && lowerInput && (
            <li
              role="option"
              aria-selected={activeIndex === createIndex}
              className={
                activeIndex === createIndex
                  ? `${styles.dropdownItem} ${styles.createOption} ${styles.dropdownItemActive}`
                  : `${styles.dropdownItem} ${styles.createOption}`
              }
              onClick={() => {
                commitTag(inputText)
                inputRef.current?.focus()
              }}
            >
              Create new tag: &ldquo;{lowerInput}&rdquo;
            </li>
          )}
        </ul>
      )}
    </div>
  )
}
