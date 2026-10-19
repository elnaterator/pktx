import { useState } from 'react'
import { useNavigate } from 'react-router'
import type { CommunicationSearchResult } from '../../types'
import {
  useAllTags,
  useCommunicationSearch,
  useContactList,
  useContactMutations,
} from '../../hooks/queries'
import { useDebouncedSearch } from '../../hooks/useDebouncedSearch'
import { Button } from '../../components/Button'
import { ListPage } from '../../components/ListPage'
import { LinkCount, ListRow } from '../../components/ListRow'
import { SearchBar } from '../../components/SearchBar'
import { TagList } from '../../components/TagList'
import { useToast } from '../../components/toast'
import { formatDate } from '../../utils/formatDate'
import { ContactPanel } from './ContactPanel'
import type { ContactCreateInput } from '../../schemas/contact'
import styles from './ContactListView.module.css'

export default function ContactListView() {
  const navigate = useNavigate()
  const { search, setSearch, debounced, isFiltered } = useDebouncedSearch()
  const [showForm, setShowForm] = useState(false)

  const listQuery = useContactList({ tags: search.tags, q: debounced.text || undefined })
  const tagsQuery = useAllTags()
  const { create } = useContactMutations()
  const { success, error } = useToast()

  const allTags = tagsQuery.data ?? []
  const hasSearchInput = isFiltered

  const commQuery = useCommunicationSearch({
    q: debounced.text || undefined,
    tags: debounced.tags,
    enabled: hasSearchInput,
  })
  const commResults: CommunicationSearchResult[] = commQuery.data ?? []
  const commSearching = commQuery.isFetching

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
    <ListPage
      title="Contacts"
      noun="contacts"
      action={
        <Button variant="link" onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Cancel' : 'New Contact'}
        </Button>
      }
      createForm={
        showForm && (
          <ContactPanel
            mode="create"
            allTags={allTags}
            onSave={handleCreate}
            onCancel={() => setShowForm(false)}
          />
        )
      }
      filters={
        <SearchBar
          value={search}
          onChange={setSearch}
          availableTags={allTags}
          placeholder="Search contacts and communications..."
        />
      }
      aside={
        hasSearchInput && (
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
                    <li key={r.id}>
                      <button type="button" className={styles.commResultItem} onClick={() => handleCommResultClick(r)}>
                        <span className={styles.commResultHeader}>
                          <span className={styles.commResultDate}>{r.date.slice(0, 10)}</span>
                          <span className={styles.commResultType}>{r.type}</span>
                          <span className={styles.commResultDir}>{r.direction}</span>
                        </span>
                        <span className={styles.commResultParent}>{r.parentName}</span>
                        {r.subject && <span className={styles.commResultSubject}>{r.subject}</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )
      }
      query={listQuery}
      items={listQuery.data ?? []}
      getKey={(contact) => contact.id}
      isFiltered={isFiltered}
      emptyMessage='No contacts yet. Click "New Contact" to add one.'
      renderItem={(contact) => (
        <ListRow to={`/contacts/${contact.id}`} linkClassName={styles.twoLine}>
          <div className={styles.itemRow1}>
            <div className={styles.itemLeft}>
              <span className={styles.itemName}>{contact.name}</span>
              {contact.relationship && (
                <span className={styles.relationshipBadge}>{contact.relationship}</span>
              )}
            </div>
            <div className={styles.itemRight}>
              <TagList tags={contact.tags} />
              <span className={styles.updatedDate}>Updated {formatDate(contact.updated_at)}</span>
            </div>
          </div>
          {(contact.company || contact.title || contact.followup_date || !!contact.link_count) && (
            <div className={styles.itemRow2}>
              {(contact.company || contact.title) && (
                <span className={styles.itemSub}>
                  {[contact.title, contact.company].filter(Boolean).join(' · ')}
                </span>
              )}
              {contact.followup_date && (
                <span className={styles.followupDate}>Follow up: {contact.followup_date}</span>
              )}
              <LinkCount count={contact.link_count} />
            </div>
          )}
        </ListRow>
      )}
    />
  )
}
