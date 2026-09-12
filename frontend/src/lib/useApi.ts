// EcoLeak AI — async data hooks with provenance (live/mock) and fallback awareness.
import { useCallback, useEffect, useRef, useState } from 'react'
import type { GroupResult, Source } from './api'

export interface AsyncResult<T> {
  data: T | null
  source: Source | null
  loading: boolean
  error: Error | null
  reload: () => void
}

/** Group fetch through liveOrMock so provenance + fallback are tracked. */
export function useGroup<T>(
  fetcher: () => Promise<GroupResult<T>>,
  deps: unknown[] = [],
): AsyncResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [source, setSource] = useState<Source | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [nonce, setNonce] = useState(0)
  const ref = useRef(fetcher)
  ref.current = fetcher

  const reload = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)
    ref.current()
      .then((res) => {
        if (!alive) return
        setData(res.data)
        setSource(res.source)
      })
      .catch((err: unknown) => {
        if (!alive) return
        setError(err instanceof Error ? err : new Error(String(err)))
      })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  return { data, source, loading, error, reload }
}

/** Plain async fetch (no mock fallback) — engine/report/quality endpoints. */
export function useAsync<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): { data: T | null; loading: boolean; error: Error | null; reload: () => void } {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [nonce, setNonce] = useState(0)
  const ref = useRef(fetcher)
  ref.current = fetcher

  const reload = useCallback(() => setNonce((n) => n + 1), [])

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)
    ref.current()
      .then((d) => { if (alive) setData(d) })
      .catch((err: unknown) => { if (alive) setError(err instanceof Error ? err : new Error(String(err))) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  return { data, loading, error, reload }
}
