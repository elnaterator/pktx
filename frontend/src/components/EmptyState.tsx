import type { ReactNode } from 'react'
import styles from './EmptyState.module.css'

interface EmptyStateProps {
  children: ReactNode
  /** Optional follow-up control, e.g. a Retry button. */
  action?: ReactNode
}

/** Quiet placeholder for an empty, filtered-out or failed list. */
export function EmptyState({ children, action }: EmptyStateProps) {
  return (
    <div className={styles.empty} role="status">
      <p className={styles.message}>{children}</p>
      {action}
    </div>
  )
}
