import { useState, useRef } from 'react'
import { Link, useNavigate } from 'react-router'
import { Link2 } from 'lucide-react'
import { ICON_SIZE } from '../../theme'
import type { CommunicationSearchResult } from '../../types'
import {
  useAllTags,
  useCommunicationSearch,
  useContactList,
  useContactMutations,
} from '../../hooks/queries'
import { SearchBar } from '../../components/SearchBar'
import { useToast } from '../../components/toast'
import { ContactPanel } from './ContactPanel'
import type { ContactCreateInput } from '../../schemas/contact'
import type { SearchValue } from '../../types'
import { Button } from '../../components/Button'
import { TagList } from '../../components/TagList'
import styles from './ContactListView.module.css'

export default function ContactListView() {
  const navigate = useNavigate()
  const [search, setSearch] = useState<SearchValue>({ tags: [], text: '' })
  const [debounced, setDebounced] = useState<SearchValue>({ tags: [], text: '' })
  const [showForm, setShowForm] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const listQuery = useContactList({ tags: search.tags, q: debounced.text || undefined })
  const tagsQuery = useAllTags()
  const { create } = useContactMutations()
  const { success, error } = useToast()

  const contacts = listQuery.data ?? []
  const allTags = tagsQuery.data ?? []

  const hasSearchInput = search.text.length > 0 || search.tags.length > 0

  const commQuery = useCommunicationSearch({
    q: debounced.text || undefined,
    tags: debounced.tags,
    enabled: hasSearchInput,
  })
  const commResults: CommunicationSearchResult[] = commQuery.data ?? []
  const commSearching = commQuery.isFetching

  const handleSearchChange = (v: SearchValue) => {
    setSearch(v)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebounced(v), 300)
  }

  const handleCreate = async (data: ContactCreateInput) => {
    try {
      await create.mutateAsync({
        name: data.name,
        email: data.email ?? undefined,
        phone: data.phone ?? undefined,
        company: data.company ?? undefined,
        title: data.title ?? undefined,
        relationship: data.relationship ?? undefined,
        linkedin_url: data.linkedin_url ?? undefined,
        location: data.location ?? undefined,
        last_contacted_date: data.last_contacted_date ?? null,
        followup_date: data.followup_date ?? null,
        notes: data.notes,
        tags: data.tags ?? [],
      })
      setShowForm(false)
      success('Contact created')
    } catch (err) {
      error(err instanceof Error ? err.message : 'Failed to create contact')
      throw err
    }
  }

  const handleCommResultClick = (result: CommunicationSearchResult) => {
    navigate(`/contacts/${result.parentId}`, { state: { expandCommId: result.id } })
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2 className={styles.heading}>Contacts</h2>
        <Button
          variant="link"
          onClick={() => setShowForm((v) => !v)}
        >
          {showForm ? 'Cancel' : 'New Contact'}
        </Button>
      </div>

      {showForm && (
        <ContactPanel
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
          placeholder="Search contacts and communications..."
        />
      </div>

      {hasSearchInput && (
        <div className={styles.commSearchCard}>
          <div className={styles.commSearchBody}>
            <h3 className={styles.commSearchHeading}>Communications</h3>
            {commSearching && <p className={styles.commSearchHint}>Searching...</p>}
            {!commSearching && commResults.length === 0 && (
              <p className={styles.commSearchHint}>No matching communications.</p>
            )}
            {commResults.length > 0 && (
              <ul className={styles.commResultList}>
                {commResults.map((r) => (
                  <li key={r.id} className={styles.commResultItem} onClick={() => handleCommResultClick(r)}>
                    <div className={styles.commResultHeader}>
                      <span className={styles.commResultDate}>{r.date.slice(0, 10)}</span>
                      <span className={styles.commResultType}>{r.type}</span>
                      <span className={styles.commResultDir}>{r.direction}</span>
                    </div>
                    <div className={styles.commResultParent}>{r.parentName}</div>
                    {r.subject && <div className={styles.commResultSubject}>{r.subject}</div>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {contacts.length === 0 ? (
        <p className={styles.empty}>No contacts yet. Click &quot;New Contact&quot; to add one.</p>
      ) : (
        <ul className={styles.list}>
          {contacts.map((contact) => (
            <li key={contact.id} className={styles.item}>
              <Link to={`/contacts/${contact.id}`} className={styles.itemLink}>
                <div className={styles.itemRow1}>
                  <div className={styles.itemLeft}>
                    <span className={styles.itemName}>{contact.name}</span>
                    {contact.relationship && (
                      <span className={styles.relationshipBadge}>{contact.relationship}</span>
                    )}
                  </div>
                  <div className={styles.itemRight}>
                    <TagList tags={contact.tags} />
                    <span className={styles.updatedDate}>Updated {new Date(contact.updated_at).toLocaleDateString()}</span>
                  </div>
                </div>
                {((contact.company || contact.title) || contact.followup_date || !!contact.link_count) && (
                  <div className={styles.itemRow2}>
                    {(contact.company || contact.title) && (
                      <span className={styles.itemSub}>
                        {[contact.title, contact.company].filter(Boolean).join(' · ')}
                      </span>
                    )}
                    {contact.followup_date && (
                      <span className={styles.followupDate}>
                        Follow up: {contact.followup_date}
                      </span>
                    )}
                    {!!contact.link_count && (
                      <span className={styles.linkCount}><Link2 size={ICON_SIZE.sm} />{contact.link_count}</span>
                    )}
                  </div>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
