import { useId, useMemo, useState } from 'react'
import { X } from 'lucide-react'
import { ICON_SIZE } from '../theme'
import type { ResourceRef, ResourceType } from '../types'
import {
  useAccomplishmentList,
  useApplicationList,
  useContactList,
  useNoteList,
  useResumeList,
} from '../hooks/queries'
import { IconButton } from './IconButton'
import { Modal } from './Modal'
import styles from './LinkPickerModal.module.css'

type TabId = 'all' | ResourceType

const TABS: { id: TabId; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'application', label: 'Applications' },
  { id: 'accomplishment', label: 'Accomplishments' },
  { id: 'resume', label: 'Resumes' },
  { id: 'note', label: 'Notes' },
  { id: 'contact', label: 'Contacts' },
]

interface LinkPickerModalProps {
  excludeRefs: ResourceRef[]
  onPick: (ref: ResourceRef) => void
  onClose: () => void
}

function isExcluded(ref: ResourceRef, excludeRefs: ResourceRef[]): boolean {
  return excludeRefs.some((e) => e.type === ref.type && e.id === ref.id)
}

export function LinkPickerModal({
  excludeRefs,
  onPick,
  onClose,
}: LinkPickerModalProps) {
  const [activeTab, setActiveTab] = useState<TabId>('all')
  const [query, setQuery] = useState('')
  const titleId = useId()

  const apps = useApplicationList()
  const accs = useAccomplishmentList()
  const resumes = useResumeList()
  const notes = useNoteList()
  const contacts = useContactList()

  const QUERIES = { application: apps, accomplishment: accs, resume: resumes, note: notes, contact: contacts }

  const allRefs = useMemo<ResourceRef[]>(() => {
    if (activeTab === 'all') {
      const refs: ResourceRef[] = [
        ...((apps.data ?? []).map((a) => ({
          type: 'application' as const,
          id: a.id,
          name: a.position ? `${a.company} – ${a.position}` : a.company,
          updatedAt: a.updated_at,
        }))),
        ...((accs.data ?? []).map((a) => ({
          type: 'accomplishment' as const,
          id: a.id,
          name: a.title,
          updatedAt: a.updated_at,
        }))),
        ...((resumes.data ?? []).map((r) => ({
          type: 'resume' as const,
          id: r.id,
          name: r.label,
          updatedAt: r.updated_at,
        }))),
        ...((notes.data ?? []).map((n) => ({
          type: 'note' as const,
          id: n.id,
          name: n.title,
          updatedAt: n.updated_at,
        }))),
        ...((contacts.data ?? []).map((c) => ({
          type: 'contact' as const,
          id: c.id,
          name: c.name,
          updatedAt: c.updated_at,
        }))),
      ]
      refs.sort((a, b) => {
        if (a.updatedAt && b.updatedAt) return b.updatedAt.localeCompare(a.updatedAt)
        return 0
      })
      return refs
    }
    switch (activeTab) {
      case 'application':
        return (apps.data ?? []).map((a) => ({
          type: 'application' as const,
          id: a.id,
          name: a.position ? `${a.company} – ${a.position}` : a.company,
          updatedAt: a.updated_at,
        }))
      case 'accomplishment':
        return (accs.data ?? []).map((a) => ({
          type: 'accomplishment' as const,
          id: a.id,
          name: a.title,
          updatedAt: a.updated_at,
        }))
      case 'resume':
        return (resumes.data ?? []).map((r) => ({
          type: 'resume' as const,
          id: r.id,
          name: r.label,
          updatedAt: r.updated_at,
        }))
      case 'note':
        return (notes.data ?? []).map((n) => ({
          type: 'note' as const,
          id: n.id,
          name: n.title,
          updatedAt: n.updated_at,
        }))
      case 'contact':
        return (contacts.data ?? []).map((c) => ({
          type: 'contact' as const,
          id: c.id,
          name: c.name,
          updatedAt: c.updated_at,
        }))
    }
  }, [activeTab, apps.data, accs.data, resumes.data, notes.data, contacts.data])

  const loading =
    activeTab === 'all'
      ? apps.isPending || accs.isPending || resumes.isPending || notes.isPending || contacts.isPending
      : QUERIES[activeTab as ResourceType].isPending

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return allRefs.filter((ref) => {
      if (isExcluded(ref, excludeRefs)) return false
      if (q && !ref.name.toLowerCase().includes(q)) return false
      return true
    })
  }, [allRefs, excludeRefs, query])

  return (
    <Modal onClose={onClose} labelledBy={titleId} className={styles.modal}>
      <div className={styles.modalHeader}>
        <h3 id={titleId} className={styles.modalTitle}>Link to resource</h3>
        <IconButton icon={X} iconSize={ICON_SIZE.lg} label="Close" tone="neutral" onClick={onClose} />
      </div>

      <div className={styles.toolbar}>
        <div className={styles.tabsScroll}>
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={`${styles.tab} ${activeTab === tab.id ? styles.tabActive : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <input
          className={styles.filterInput}
          type="text"
          placeholder="filter..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />
      </div>

      <div className={styles.resultsList}>
        {loading ? (
          <div className={styles.loading}>Loading...</div>
        ) : filtered.length === 0 ? (
          <div className={styles.empty}>No results</div>
        ) : (
          filtered.map((ref) => (
            <button
              key={`${ref.type}/${ref.id}`}
              className={styles.resultRow}
              onClick={() => onPick(ref)}
            >
              {activeTab === 'all' && (
                <span className={styles.typeBadge}>{ref.type}</span>
              )}
              <span className={styles.resultName}>{ref.name}</span>
            </button>
          ))
        )}
      </div>
    </Modal>
  )
}
