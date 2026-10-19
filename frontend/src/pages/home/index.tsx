import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { useUser } from '@clerk/clerk-react'
import { Briefcase, FileText, Trophy, StickyNote, Users, Bot } from 'lucide-react'
import { ICON_SIZE } from '../../theme'
import {
  useAccomplishmentList,
  useApplicationList,
  useContactList,
  useGlobalSearch,
  useNoteList,
  useResumeList,
  useAllTags,
} from '../../hooks/queries'
import { SearchBar } from '../../components/SearchBar'
import type { SearchResult, SearchValue } from '../../types'
import styles from './HomeView.module.css'

// ─── Search results ────────────────────────────────────────────────────────────

const TYPE_ORDER = ['resume', 'application', 'accomplishment', 'note', 'contact', 'communication']
const TYPE_LABELS: Record<string, string> = {
  resume: 'Resumes',
  application: 'Applications',
  accomplishment: 'Accomplishments',
  note: 'Notes',
  contact: 'Contacts',
  communication: 'Communications',
}

function SearchResults({ results, loading }: { results: SearchResult[]; loading: boolean }) {
  if (loading) {
    return <p className={styles.searchHint}>Searching...</p>
  }

  if (results.length === 0) {
    return <p className={styles.searchHint}>No results.</p>
  }

  const grouped = new Map<string, SearchResult[]>()
  for (const r of results) {
    if (!grouped.has(r.type)) grouped.set(r.type, [])
    grouped.get(r.type)!.push(r)
  }

  const orderedTypes = TYPE_ORDER.filter((t) => grouped.has(t))

  return (
    <div className={styles.searchResults}>
      {orderedTypes.map((type) => {
        const items = grouped.get(type)!
        return (
          <div key={type} className={styles.searchGroup}>
            <div className={styles.searchGroupHeader}>
              {TYPE_LABELS[type] ?? type} <span className={styles.searchGroupCount}>{items.length}</span>
            </div>
            <ul className={styles.searchResultList}>
              {items.map((item) => (
                <li key={`${item.type}-${item.id}`}>
                  <Link to={item.url} className={styles.searchResultRow}>
                    <span className={styles.searchResultTitle}>{item.title}</span>
                    {item.subtitle && (
                      <span className={styles.searchResultSub}>{item.subtitle}</span>
                    )}
                    {item.snippet && (
                      <span className={styles.searchResultSnippet}>{item.snippet}</span>
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )
      })}
    </div>
  )
}

// ─── Ideas ────────────────────────────────────────────────────────────────────

const IDEAS = [
  {
    icon: Bot,
    title: 'Chat with your own career data',
    body: 'Connect Claude, ChatGPT, or another assistant over MCP and ask it to draft a cover letter from your real accomplishments.',
  },
  {
    icon: Briefcase,
    title: 'Pull full context for one application',
    body: 'Get every linked accomplishment, contact, and note for a job in a single call — built for interview prep.',
  },
  {
    icon: FileText,
    title: 'Link the story behind each resume',
    body: 'Connect a resume to the applications and accomplishments that justify it, so nothing lives in a silo.',
  },
  {
    icon: Trophy,
    title: 'Bank wins before you need them',
    body: 'Log accomplishments as they happen so review season and resume rewrites start with proof, not memory.',
  },
  {
    icon: Users,
    title: 'Keep every touchpoint on the record',
    body: 'Attach calls and emails to a contact and see your whole relationship with a recruiter in one timeline.',
  },
  {
    icon: StickyNote,
    title: 'Tag once, find everywhere',
    body: 'A shared tag like "python" or "remote" surfaces the resumes, notes, and accomplishments that share it — search across all of it at once.',
  },
]

const IDEA_INTERVAL_MS = 7000

function IdeaScroller() {
  const [index, setIndex] = useState(0)

  useEffect(() => {
    const id = setInterval(() => {
      setIndex((i) => (i + 1) % IDEAS.length)
    }, IDEA_INTERVAL_MS)
    return () => clearInterval(id)
  }, [])

  const { icon: Icon, title, body } = IDEAS[index]

  return (
    <div className={styles.ideaScroller}>
      <div className={styles.ideaCard} key={index}>
        <Icon size={ICON_SIZE['2xl']} className={styles.ideaIcon} />
        <span className={styles.ideaTitle}>{title}</span>
        <p className={styles.ideaBody}>{body}</p>
      </div>
      <div className={styles.ideaDots}>
        {IDEAS.map((idea, i) => (
          <button
            key={idea.title}
            type="button"
            className={`${styles.ideaDot}${i === index ? ` ${styles.ideaDotActive}` : ''}`}
            aria-label={`Show idea ${i + 1}: ${idea.title}`}
            aria-current={i === index}
            onClick={() => setIndex(i)}
          />
        ))}
      </div>
    </div>
  )
}

// ─── Stats ────────────────────────────────────────────────────────────────────

const TERMINAL_STATUSES = new Set(['Rejected', 'Withdrawn', 'Accepted'])

// ─── Home ─────────────────────────────────────────────────────────────────────

export default function HomeView() {
  const { user } = useUser()
  const firstName = user?.firstName ?? null

  const [searchValue, setSearchValue] = useState<SearchValue>({ tags: [], text: '' })
  const [debouncedSearch, setDebouncedSearch] = useState<SearchValue>({ tags: [], text: '' })
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const tagsQuery = useAllTags()
  const allTags = tagsQuery.data ?? []

  const hasSearch = debouncedSearch.text.length > 0 || debouncedSearch.tags.length > 0
  const searchQuery = useGlobalSearch({
    q: debouncedSearch.text || undefined,
    tags: debouncedSearch.tags.length > 0 ? debouncedSearch.tags : undefined,
    enabled: hasSearch,
  })

  const handleSearchChange = (v: SearchValue) => {
    setSearchValue(v)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedSearch(v), 300)
  }

  const resumes = useResumeList()
  const applications = useApplicationList()
  const notes = useNoteList()
  const accomplishments = useAccomplishmentList()
  const contacts = useContactList()

  const ready =
    resumes.isSuccess &&
    applications.isSuccess &&
    notes.isSuccess &&
    accomplishments.isSuccess &&
    contacts.isSuccess

  const stats = ready
    ? {
        resumes: resumes.data.length,
        applications: applications.data.length,
        activeApplications: applications.data.filter(
          (a) => !TERMINAL_STATUSES.has(a.status),
        ).length,
        notes: notes.data.length,
        accomplishments: accomplishments.data.length,
        contacts: contacts.data.length,
      }
    : null

  return (
    <div className={styles.container}>
      <div className={styles.statsGrid}>
        <Link to="/applications" className={styles.statCard}>
          <span className={styles.statLabel}>Applications</span>
          <span className={styles.statValue}>{stats === null ? '—' : stats.applications}</span>
          {stats !== null && stats.activeApplications > 0 && (
            <span className={styles.statSub}>{stats.activeApplications} active</span>
          )}
        </Link>

        <Link to="/resumes" className={styles.statCard}>
          <span className={styles.statLabel}>Resumes</span>
          <span className={styles.statValue}>{stats === null ? '—' : stats.resumes}</span>
        </Link>

        <Link to="/accomplishments" className={styles.statCard}>
          <span className={styles.statLabel}>Accomplishments</span>
          <span className={styles.statValue}>{stats === null ? '—' : stats.accomplishments}</span>
        </Link>

        <Link to="/notes" className={styles.statCard}>
          <span className={styles.statLabel}>Notes</span>
          <span className={styles.statValue}>{stats === null ? '—' : stats.notes}</span>
        </Link>

        <Link to="/contacts" className={styles.statCard}>
          <span className={styles.statLabel}>Contacts</span>
          <span className={styles.statValue}>{stats === null ? '—' : stats.contacts}</span>
        </Link>
      </div>

      <div className={styles.globalSearch}>
        <SearchBar
          value={searchValue}
          onChange={handleSearchChange}
          availableTags={allTags}
          placeholder="Search everything..."
        />
        {hasSearch ? (
          <SearchResults
            results={searchQuery.data ?? []}
            loading={searchQuery.isFetching}
          />
        ) : (
          <div className={styles.intro}>
            <p className={styles.introWelcome}>
              {firstName ? `Welcome back, ${firstName}.` : 'Welcome back.'}
            </p>
            <p className={styles.introSlogan}>
              Your career, organized — resumes, applications, accomplishments, and contacts, all in one searchable place.
            </p>
            <IdeaScroller />
          </div>
        )}
      </div>
    </div>
  )
}
