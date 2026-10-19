import { useState, useRef } from 'react'
import { Link } from 'react-router'
import { Link2 } from 'lucide-react'
import { ICON_SIZE } from '../../theme'
import {
  useAccomplishmentList,
  useAccomplishmentMutations,
  useAllTags,
} from '../../hooks/queries'
import { SearchBar } from '../../components/SearchBar'
import { useToast } from '../../components/toast'
import { AccomplishmentPanel } from './AccomplishmentPanel'
import type { AccomplishmentCreateInput } from '../../schemas/accomplishment'
import type { SearchValue } from '../../types'
import { Button } from '../../components/Button'
import { TagList } from '../../components/TagList'
import styles from './AccomplishmentListView.module.css'

export default function AccomplishmentListView() {
  const [search, setSearch] = useState<SearchValue>({ tags: [], text: '' })
  const [debouncedQ, setDebouncedQ] = useState('')
  const [showForm, setShowForm] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const listQuery = useAccomplishmentList({ tags: search.tags, q: debouncedQ || undefined })
  const tagsQuery = useAllTags()
  const { create } = useAccomplishmentMutations()
  const { success, error } = useToast()

  const accomplishments = listQuery.data ?? []
  const allTags = tagsQuery.data ?? []

  const handleSearchChange = (v: SearchValue) => {
    setSearch(v)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedQ(v.text), 300)
  }

  const handleCreate = async (data: AccomplishmentCreateInput) => {
    try {
      await create.mutateAsync({
        title: data.title,
        situation: data.situation ?? undefined,
        task: data.task ?? undefined,
        action: data.action ?? undefined,
        result: data.result ?? undefined,
        accomplishment_date: data.accomplishment_date ?? null,
        tags: data.tags ?? [],
      })
      setShowForm(false)
      success('Accomplishment created')
    } catch (err) {
      error(err instanceof Error ? err.message : 'Failed to create accomplishment')
      throw err
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2 className={styles.heading}>Accomplishments</h2>
        <Button
          variant="link"
          onClick={() => setShowForm((v) => !v)}
        >
          {showForm ? 'Cancel' : 'New Accomplishment'}
        </Button>
      </div>

      {showForm && (
        <AccomplishmentPanel
          mode="create"
          allTags={allTags}
          onSave={handleCreate}
          onCancel={() => setShowForm(false)}
        />
      )}

      <div className={styles.filters}>
        <SearchBar
          value={search}
          onChange={handleSearchChange}
          availableTags={allTags}
          placeholder="Search accomplishments..."
        />
      </div>

      {accomplishments.length === 0 ? (
        <p className={styles.empty}>No accomplishments yet. Click &quot;New Accomplishment&quot; to add one.</p>
      ) : (
        <ul className={styles.list}>
          {accomplishments.map((acc) => (
            <li key={acc.id} className={styles.item}>
              <Link to={`/accomplishments/${acc.id}`} className={styles.itemLink}>
                <div className={styles.itemMain}>
                  <span className={styles.itemTitle}>{acc.title}</span>
                </div>
                <TagList tags={acc.tags} />
                <div className={styles.itemMeta}>
                  {acc.accomplishment_date && (
                    <span>{acc.accomplishment_date}</span>
                  )}
                  {!!acc.link_count && (
                    <span className={styles.linkCount}><Link2 size={ICON_SIZE.sm} />{acc.link_count}</span>
                  )}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
