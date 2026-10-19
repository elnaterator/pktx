import { forwardRef, type ButtonHTMLAttributes } from 'react'
import type { LucideIcon } from 'lucide-react'
import { ICON_SIZE } from '../theme'
import { cx } from '../utils/cx'
import styles from './button.module.css'

export type IconButtonTone = 'accent' | 'danger' | 'neutral'

const TONE_CLASS: Record<IconButtonTone, string> = {
  accent: styles.accent,
  danger: styles.dangerTone,
  neutral: styles.neutral,
}

interface IconButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children' | 'aria-label'> {
  icon: LucideIcon
  /** Accessible name (icon-only buttons have no visible text). */
  label: string
  /** Hover colour: accent for edit/save, danger for delete/cancel. */
  tone?: IconButtonTone
  iconSize?: number
}

/** Muted icon-only button that takes a tone colour on hover. */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { icon: Icon, label, tone = 'accent', iconSize = ICON_SIZE.md, type = 'button', className, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      className={cx(styles.iconButton, TONE_CLASS[tone], className)}
      {...rest}
    >
      <Icon size={iconSize} aria-hidden="true" />
    </button>
  )
})
