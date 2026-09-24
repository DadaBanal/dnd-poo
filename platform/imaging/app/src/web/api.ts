// The page's side of the API. Every answer is checked against the shared
// schemas before the page uses it.
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Me, Studies, type StudiesQuery } from '../shared/api.ts';

export class SignedOut extends Error {}

async function get<T>(path: string, schema: { parse: (v: unknown) => T }, signal?: AbortSignal): Promise<T> {
  const r = await fetch(`/pmc/api${path}`, { signal, headers: { Accept: 'application/json' } });
  // No session any more: only a page load can start a sign-in, so say so.
  if (r.status === 401) throw new SignedOut('signed out');
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return schema.parse(await r.json());
}

export const fetchMe = (signal?: AbortSignal) => get('/me', Me, signal);

export function fetchStudies(q: Partial<StudiesQuery>, signal?: AbortSignal): Promise<Studies> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(q)) if (v !== undefined && v !== '') params.set(k, String(v));
  return get(`/studies?${params}`, Studies, signal);
}

// "The studies changed": the server says so the moment the engine does, and
// the worklist asks again. Reconnects by itself; `live` says whether it is
// connected now.
export function useLiveStudies(): boolean {
  const client = useQueryClient();
  const [live, setLive] = useState(false);
  useEffect(() => {
    const events = new EventSource('/pmc/api/events');
    events.addEventListener('hello', () => setLive(true));
    events.addEventListener('studies', () => void client.invalidateQueries({ queryKey: ['studies'] }));
    events.onerror = () => setLive(false);
    return () => events.close();
  }, [client]);
  return live;
}
