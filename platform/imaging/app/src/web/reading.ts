// The reading list's data and actions, shared by the list page and the reading
// room: who is signed in, the studies for the filters in force, and claiming
// or marking read (with the one-line notices they produce).
import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { READERS, modalityGroups, type Me, type Study, type WorklistSearch } from '../shared/api.ts';
import { claimStudy, fetchMe, fetchStudies, markRead, markUnread, releaseStudy, type Outcome } from './api.ts';
import { personName } from './format.ts';

export const PAGE = 50;

export const useMe = () => useQuery({ queryKey: ['me'], queryFn: ({ signal }) => fetchMe(signal), staleTime: 60_000 });

export const canRead = (me: Me | undefined) => me?.roles.some((r) => READERS.includes(r)) ?? false;

// The filters in the address, as the server takes them.
export function listParams(search: WorklistSearch) {
  return {
    q: search.q,
    mod: modalityGroups(search.mod).join(',') || undefined,
    range: search.range ?? '7d',
    sort: search.sort ?? 'time',
    dir: search.dir,
    mine: search.mine,
    unread: search.unread,
  };
}
export type ListParams = ReturnType<typeof listParams>;

// The studies for the filters in force. While the filters change, the rows
// already on screen stay until the new ones arrive: no empty list, no
// "loading" flash.
export function useStudies(params: ListParams) {
  const studies = useInfiniteQuery({
    queryKey: ['studies', params],
    queryFn: ({ pageParam, signal }) => fetchStudies({ ...params, since: pageParam, limit: PAGE }, signal),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => (last.more && last.sortedBy === 'engine' ? pages.length * PAGE : undefined),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  });
  const rows = useMemo(() => studies.data?.pages.flatMap((p) => p.studies) ?? [], [studies.data]);
  const byId = useMemo(() => new Map(rows.map((s) => [s.id, s])), [rows]);
  const cut = studies.data?.pages.some((p) => p.more && p.sortedBy === 'page') ?? false;
  const total = studies.data?.pages[0]?.total;
  return { studies, rows, byId, cut, total };
}

// A claim or a read, made or undone, and (when made) whether it went through.
type Change = { did: 'undo'; study: Study } | { did: 'do'; study: Study; result: Outcome };

// Claiming and marking read, as stable callbacks (the table is memoized on
// them), and the notice each one leaves for six seconds.
export function useReadingActions(me: Me | undefined) {
  const client = useQueryClient();
  const [notice, setNotice] = useState<string>();
  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(undefined), 6_000);
    return () => clearTimeout(t);
  }, [notice]);
  const changed = () => void client.invalidateQueries({ queryKey: ['studies'] });
  const username = me?.username;

  const toggleClaim = useMutation({
    mutationFn: async (s: Study): Promise<Change> => {
      if (s.claim?.reader === username) {
        await releaseStudy(s.studyUid);
        return { did: 'undo', study: s };
      }
      return { did: 'do', study: s, result: await claimStudy(s.studyUid) };
    },
    onSuccess: (r) => {
      const who = personName(r.study.patientName);
      if (r.did === 'undo') setNotice(`You released ${who}.`);
      else if (r.result.ok) setNotice(`You claimed ${who}.`);
      else setNotice(`${who} is already claimed by ${r.result.by}.`);
      changed();
    },
    onError: () => setNotice('That did not go through. Try again.'),
  });

  const toggleRead = useMutation({
    mutationFn: async (s: Study): Promise<Change> => {
      if (s.read?.reader === username) {
        await markUnread(s.studyUid);
        return { did: 'undo', study: s };
      }
      return { did: 'do', study: s, result: await markRead(s.studyUid) };
    },
    onSuccess: (r) => {
      const who = personName(r.study.patientName);
      if (r.did === 'undo') setNotice(`You marked ${who} unread.`);
      else if (r.result.ok) setNotice(`You marked ${who} read.`);
      else setNotice(`${who} is claimed by ${r.result.by}.`);
      changed();
    },
    onError: () => setNotice('That did not go through. Try again.'),
  });

  const latest = useRef({ toggleClaim, toggleRead, able: canRead(me) });
  latest.current = { toggleClaim, toggleRead, able: canRead(me) };
  const onClaim = useCallback((s: Study) => {
    const { toggleClaim: claim, able } = latest.current;
    if (able && !claim.isPending) claim.mutate(s);
  }, []);
  const onRead = useCallback((s: Study) => {
    const { toggleRead: read, able } = latest.current;
    if (able && !read.isPending) read.mutate(s);
  }, []);
  return { notice, onClaim, onRead, canRead: canRead(me) };
}
