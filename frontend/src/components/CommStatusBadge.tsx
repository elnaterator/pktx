import { COMM_STATUS_LABELS, commLabel, type CommStatus } from '../schemas/communication'
import { cx } from '../utils/cx'
import styles from './CommStatusBadge.module.css'

const STATUS_CLASS: Record<CommStatus, string> = {
  draft: styles.draft,
  ready: styles.ready,
  sent: styles.sent,
  archived: styles.archived,
}

/** Communication status pill (draft / ready / sent / archived). */
export function CommStatusBadge({ status }: { status: string }) {
  return (
    <span className={cx(styles.badge, STATUS_CLASS[status as CommStatus])}>
      {commLabel(COMM_STATUS_LABELS, status)}
    </span>
  )
}
