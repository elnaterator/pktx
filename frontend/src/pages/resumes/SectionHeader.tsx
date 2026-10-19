import type { ReactNode } from 'react'
import styles from './SectionHeader.module.css'

interface SectionHeaderProps {
  title: string
  /** Buttons for the top right, e.g. "Add Experience". */
  children?: ReactNode
}

/** A resume section's title with its actions on the right. */
export default function SectionHeader({ title, children }: SectionHeaderProps) {
  return (
    <div className={styles.header}>
      <h2 className={styles.title}>{title}</h2>
      {children && <div className={styles.actions}>{children}</div>}
    </div>
  )
}
