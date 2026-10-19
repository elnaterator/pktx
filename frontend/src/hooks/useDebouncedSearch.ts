import { useCallback, useEffect, useRef, useState } from 'react'
import type { SearchValue } from '../types'

const EMPTY: SearchValue = { tags: [], text: '' }

/**
 * Search box state with a debounced copy for queries. `search` updates on
 * every keystroke (drive the input and tag filters from it); `debounced`
 * trails by `delay` ms (use its `text` for server-side text search).
 */
export function useDebouncedSearch(delay = 300) {
  const [search, setSearchState] = useState<SearchValue>(EMPTY)
  const [debounced, setDebounced] = useState<SearchValue>(EMPTY)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  useEffect(() => () => clearTimeout(timer.current), [])

  const setSearch = useCallback(
    (value: SearchValue) => {
      setSearchState(value)
      clearTimeout(timer.current)
      timer.current = setTimeout(() => setDebounced(value), delay)
    },
    [delay],
  )

  const isFiltered = search.text.trim().length > 0 || search.tags.length > 0

  return { search, setSearch, debounced, isFiltered }
}
