import styles from './TagList.module.css'

interface TagListProps {
  tags: string[]
}

/** Read-only row of tag badges. Renders nothing for an empty list. */
export function TagList({ tags }: TagListProps) {
  if (tags.length === 0) return null
  return (
    <div className={styles.list}>
      {tags.map((tag) => (
        <span key={tag} className={styles.badge}>
          {tag}
        </span>
      ))}
    </div>
  )
}
