import type { ApplicationStatus } from '../../schemas/application'
import { cx } from '../../utils/cx'
import styles from './StatusBadge.module.css'

const STATUS_CLASS: Record<ApplicationStatus, string> = {
  Interested: styles.interested,
  Applied: styles.applied,
  'Phone Screen': styles.phoneScreen,
  Interview: styles.interview,
  Offer: styles.offer,
  Rejected: styles.rejected,
  Withdrawn: styles.withdrawn,
  Accepted: styles.accepted,
}

/** Application status as a coloured dot + label per pipeline stage (unknown → neutral). */
export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={cx(styles.badge, STATUS_CLASS[status as ApplicationStatus])}>{status}</span>
  )
}
