import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useStoredState } from '../../hooks/useStoredState'

const isString = (v: unknown): v is string => typeof v === 'string'

describe('useStoredState', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => vi.restoreAllMocks())

  it('reads, writes, and persists a value', () => {
    const { result, unmount } = renderHook(() => useStoredState('k', 'a', isString))
    expect(result.current[0]).toBe('a')
    act(() => result.current[1]('b'))
    expect(result.current[0]).toBe('b')
    unmount()
    expect(renderHook(() => useStoredState('k', 'a', isString)).result.current[0]).toBe('b')
  })

  it('falls back to the initial value for invalid or corrupt data', () => {
    localStorage.setItem('k', '42')
    expect(renderHook(() => useStoredState('k', 'a', isString)).result.current[0]).toBe('a')
    localStorage.setItem('k', '{not json')
    expect(renderHook(() => useStoredState('k', 'a', isString)).result.current[0]).toBe('a')
  })

  it('keeps working when storage throws', () => {
    vi.spyOn(localStorage, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const { result } = renderHook(() => useStoredState('k', 'a', isString))
    expect(result.current[0]).toBe('a')
    act(() => result.current[1]('b'))
    expect(result.current[0]).toBe('b')
  })
})
