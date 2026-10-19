import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { Link2 } from 'lucide-react'
import { ICON_SIZE } from '../theme'
import { cx } from '../utils/cx'
import styles from './listRow.module.css'

interface ListRowProps {
  to: string
  children: ReactNode
  /** Content after the row link (e.g. an external link, which can't nest in it). */
  after?: ReactNode
  /** Layout override for the link area (e.g. a two-line row). */
  linkClassName?: string
}

/** One clickable row of a resource list. */
export function ListRow({ to, children, after, linkClassName }: ListRowProps) {
  return (
    <li className={styles.item}>
      <Link to={to} className={cx(styles.itemLink, linkClassName)}>
        {children}
      </Link>
      {after}
    </li>
  )
}

/** Left part of a row: title plus inline badges. */
export function ListRowMain({ children }: { children: ReactNode }) {
  return <div className={styles.itemMain}>{children}</div>
}

export function ListRowTitle({ children }: { children: ReactNode }) {
  return <span className={styles.title}>{children}</span>
}

/** Right-hand muted metadata (dates, counts). */
export function ListRowMeta({ children }: { children: ReactNode }) {
  return <div className={styles.itemMeta}>{children}</div>
}

/** "🔗 3" — number of linked resources; renders nothing for zero. */
export function LinkCount({ count }: { count?: number }) {
  if (!count) return null
  return (
    <span className={styles.linkCount} title={`${count} linked`}>
      <Link2 size={ICON_SIZE.sm} aria-hidden="true" />
      {count}
    </span>
  )
}
