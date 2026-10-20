import { useEffect, useRef, useState } from 'react'
import { CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react'
import { ICON_SIZE } from '../theme'
import styles from './DateInput.module.css'

interface DateInputProps {
  id?: string
  value: string
  onChange: (value: string) => void
  className?: string
  placeholder?: string
  invalid?: boolean
  /** Let the calendar go down to a day (`YYYY-MM-DD`); otherwise it stops at a month. */
  days?: boolean
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
] // prettier-ignore
const WEEKDAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']
const PARTIAL = /^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$/

const pad = (n: number) => String(n).padStart(2, '0')

/** Year / month / day the field currently holds (all optional). */
function parse(value: string): { year?: number; month?: number; day?: number } {
  const m = PARTIAL.exec(value.trim())
  if (!m) return {}
  return {
    year: Number(m[1]),
    month: m[2] ? Number(m[2]) : undefined,
    day: m[3] ? Number(m[3]) : undefined,
  }
}

interface CalendarProps {
  value: string
  days: boolean
  onPick: (value: string) => void
}

/** Year stepper + month grid, then (when `days`) a day grid for the chosen month. */
function Calendar({ value, days, onPick }: CalendarProps) {
  const current = parse(value)
  const [year, setYear] = useState(current.year ?? new Date().getFullYear())
  /** Month whose days are showing; null while choosing a month. */
  const [month, setMonth] = useState<number | null>(null)

  if (month !== null) {
    const count = new Date(year, month, 0).getDate()
    const offset = new Date(year, month - 1, 1).getDay()
    const step = (delta: number) => {
      const d = new Date(year, month - 1 + delta, 1)
      setYear(d.getFullYear())
      setMonth(d.getMonth() + 1)
    }
    return (
      <div className={styles.calendar}>
        <div className={styles.calendarHeader}>
          <button type="button" onClick={() => step(-1)} aria-label="Previous month">
            <ChevronLeft size={ICON_SIZE.md} aria-hidden="true" />
          </button>
          <span className={styles.calendarTitle}>
            {MONTH_NAMES[month - 1]} {year}
          </span>
          <button type="button" onClick={() => step(1)} aria-label="Next month">
            <ChevronRight size={ICON_SIZE.md} aria-hidden="true" />
          </button>
        </div>
        <div className={styles.weekdays} aria-hidden="true">
          {WEEKDAYS.map((d) => (
            <span key={d}>{d}</span>
          ))}
        </div>
        <div className={styles.dayGrid}>
          {Array.from({ length: offset }, (_, i) => (
            <span key={`blank-${i}`} />
          ))}
          {Array.from({ length: count }, (_, i) => i + 1).map((day) => (
            <button
              key={day}
              type="button"
              className={
                current.year === year && current.month === month && current.day === day
                  ? styles.selected
                  : undefined
              }
              aria-label={`${MONTH_NAMES[month - 1]} ${day}, ${year}`}
              onClick={() => onPick(`${year}-${pad(month)}-${pad(day)}`)}
            >
              {day}
            </button>
          ))}
        </div>
        <div className={styles.calendarFooter}>
          <button type="button" onClick={() => setMonth(null)}>
            Months
          </button>
          <button type="button" onClick={() => onPick(`${year}-${pad(month)}`)}>
            Month only
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.calendar}>
      <div className={styles.calendarHeader}>
        <button type="button" onClick={() => setYear(year - 1)} aria-label="Previous year">
          <ChevronLeft size={ICON_SIZE.md} aria-hidden="true" />
        </button>
        <input
          type="number"
          className={styles.year}
          value={year}
          min={1900}
          max={2100}
          aria-label="Year"
          onChange={(e) => {
            const y = Number(e.target.value)
            if (Number.isInteger(y) && y >= 1000 && y <= 9999) setYear(y)
          }}
        />
        <button type="button" onClick={() => setYear(year + 1)} aria-label="Next year">
          <ChevronRight size={ICON_SIZE.md} aria-hidden="true" />
        </button>
      </div>
      <div className={styles.monthGrid}>
        {MONTHS.map((label, i) => (
          <button
            key={label}
            type="button"
            className={current.year === year && current.month === i + 1 ? styles.selected : undefined}
            aria-label={`${MONTH_NAMES[i]} ${year}`}
            onClick={() => (days ? setMonth(i + 1) : onPick(`${year}-${pad(i + 1)}`))}
          >
            {label}
          </button>
        ))}
      </div>
      <div className={styles.calendarFooter}>
        <button type="button" onClick={() => onPick('')}>
          Clear
        </button>
        <button type="button" onClick={() => onPick(String(year))}>
          Year only
        </button>
      </div>
    </div>
  )
}

/**
 * Partial ISO date (`YYYY`, `YYYY-MM`, `YYYY-MM-DD`): type it, or choose it from an
 * in-page calendar (year and month, then a day when `days` is set). The calendar is
 * our own rather than the browser's, so it looks and behaves the same everywhere.
 */
export function DateInput({
  id,
  value,
  onChange,
  className,
  placeholder = 'YYYY-MM',
  invalid,
  days = false,
}: DateInputProps) {
  const [open, setOpen] = useState(false)
  const wrap = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div
      className={styles.wrap}
      ref={wrap}
      onKeyDown={(e) => {
        // Escape closes the calendar first; mark it handled so an enclosing
        // form or dialog doesn't also cancel.
        if (e.key === 'Escape' && open) {
          e.preventDefault()
          setOpen(false)
        }
      }}
    >
      <input
        id={id}
        type="text"
        className={className}
        value={value}
        placeholder={placeholder}
        aria-invalid={invalid}
        autoComplete="off"
        onChange={(e) => onChange(e.target.value)}
      />
      <button
        type="button"
        className={styles.pick}
        onClick={() => setOpen((o) => !o)}
        aria-label="Choose date"
        aria-expanded={open}
      >
        <CalendarDays size={ICON_SIZE.md} aria-hidden="true" />
      </button>
      {open && (
        <div className={styles.popover} role="dialog" aria-label="Choose date">
          <Calendar
            value={value}
            days={days}
            onPick={(v) => {
              onChange(v)
              setOpen(false)
            }}
          />
        </div>
      )}
    </div>
  )
}
