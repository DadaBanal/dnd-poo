// The worklist: every study a person may see, newest first, filtered in the
// URL so any view is a link. Enter or a double-click opens the study in the
// viewer, in one named window that stays on the second screen.
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearch } from '@tanstack/react-router';
import { ExternalLink, RotateCcw, Search, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  Button, Cell, Column, Input, Link, Row, SearchField, Table, TableBody, TableHeader,
  ToggleButton, ToggleButtonGroup, type Key, type Selection, type SortDescriptor,
} from 'react-aria-components';
import {
  GROUP_KEYS, MODALITY_GROUPS, READERS, modalityGroups, type ModalityGroup, type Study, type WorklistSearch,
} from '../shared/api.ts';
import { SignedOut, claimStudy, fetchMe, fetchStudies, markOpened, releaseStudy } from './api.ts';
import { ago, personName, sexAge, studyMoment, when } from './format.ts';

const PAGE = 50;
const VIEWER_WINDOW = 'pmc-viewer';
const RANGE_LABELS = { today: 'Today', '3d': '3 days', '7d': '7 days', '30d': '30 days', all: 'All' } as const;
const COLUMN_SORT = { time: 'time', patient: 'patient', accession: 'accession' } as const;

export const viewerUrl = (s: Study) => `/viewer?StudyInstanceUIDs=${encodeURIComponent(s.studyUid)}`;

function openViewer(s: Study) {
  markOpened(s.studyUid);
  window.open(viewerUrl(s), VIEWER_WINDOW);
}

function useNow(everyMs: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(t);
  }, [everyMs]);
  return now;
}

export function Worklist() {
  const search = useSearch({ from: '/' });
  const navigate = useNavigate({ from: '/' });
  const set = (patch: Partial<WorklistSearch>) =>
    void navigate({ search: (prev) => ({ ...prev, ...patch }), replace: true });

  const me = useQuery({ queryKey: ['me'], queryFn: ({ signal }) => fetchMe(signal), staleTime: 60_000 });
  const referrerOnly = me.data?.roles.length === 1 && me.data.roles[0] === 'pmc-referrer';
  const canClaim = me.data?.roles.some((r) => READERS.includes(r)) ?? false;
  const client = useQueryClient();
  const [notice, setNotice] = useState<string>();
  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(undefined), 6_000);
    return () => clearTimeout(t);
  }, [notice]);
  const toggleClaim = useMutation({
    mutationFn: async (s: Study) => {
      if (s.claim?.reader === me.data?.email) {
        await releaseStudy(s.studyUid);
        return { released: s };
      }
      return { claimed: s, result: await claimStudy(s.studyUid) };
    },
    onSuccess: (r) => {
      if ('result' in r && r.result && !r.result.ok) {
        setNotice(`${personName(r.claimed.patientName)} is already claimed by ${r.result.by}.`);
      } else if ('released' in r && r.released) {
        setNotice(`You released ${personName(r.released.patientName)}.`);
      } else if ('claimed' in r && r.claimed) {
        setNotice(`You claimed ${personName(r.claimed.patientName)}.`);
      }
      void client.invalidateQueries({ queryKey: ['studies'] });
    },
    onError: () => setNotice('That did not go through. Try again.'),
  });

  const range = search.range ?? '7d';
  const sort = search.sort ?? 'time';
  const groups = modalityGroups(search.mod);
  const params = { q: search.q, mod: groups.join(',') || undefined, range, sort, dir: search.dir, mine: search.mine };

  const studies = useInfiniteQuery({
    queryKey: ['studies', params],
    queryFn: ({ pageParam, signal }) => fetchStudies({ ...params, since: pageParam, limit: PAGE }, signal),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => (last.more && last.sortedBy === 'engine' ? pages.length * PAGE : undefined),
    refetchInterval: 60_000,
  });
  const rows = useMemo(() => studies.data?.pages.flatMap((p) => p.studies) ?? [], [studies.data]);
  const byId = useMemo(() => new Map(rows.map((s) => [s.id, s])), [rows]);
  const cut = studies.data?.pages.some((p) => p.more && p.sortedBy === 'page') ?? false;

  const [selected, setSelected] = useState<Selection>(new Set());
  const now = useNow(30_000);
  const searchInput = useRef<HTMLInputElement>(null);
  const table = useRef<HTMLTableElement>(null);

  // "a" claims or releases the study the keyboard is on.
  const claimKey = useRef<(id: string) => void>(() => {});
  claimKey.current = (id: string) => {
    const s = byId.get(id);
    if (s && canClaim && !toggleClaim.isPending) toggleClaim.mutate(s);
  };

  // "/" finds, j and k move, a claims, Escape leaves the search box.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement;
      if (e.key === '/' && !typing) {
        e.preventDefault();
        searchInput.current?.focus();
      } else if ((e.key === 'j' || e.key === 'k') && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const list = [...(table.current?.querySelectorAll<HTMLElement>('tbody [role="row"]') ?? [])];
        if (!list.length) return;
        const at = list.findIndex((r) => r.contains(document.activeElement));
        const next = at < 0 ? 0 : Math.min(list.length - 1, Math.max(0, at + (e.key === 'j' ? 1 : -1)));
        list[next]?.focus();
        e.preventDefault();
      } else if (e.key === 'a' && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const row = (document.activeElement as HTMLElement | null)?.closest<HTMLElement>('tbody [role="row"]');
        const id = row?.dataset.key;
        if (id) {
          claimKey.current(id);
          e.preventDefault();
        }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  const sortDescriptor: SortDescriptor = {
    column: sort,
    direction: (search.dir ?? (sort === 'time' ? 'desc' : 'asc')) === 'asc' ? 'ascending' : 'descending',
  };
  const onSortChange = (d: SortDescriptor) =>
    set({ sort: COLUMN_SORT[d.column as keyof typeof COLUMN_SORT] ?? 'time', dir: d.direction === 'ascending' ? 'asc' : 'desc' });

  const title = referrerOnly ? 'Studies shared with you' : 'PMC imaging studies';
  const signedOut = studies.error instanceof SignedOut || me.error instanceof SignedOut;

  return (
    <section aria-labelledby="wl-title" className="flex min-h-0 flex-1 flex-col gap-4 px-4 py-5 md:px-6">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div>
          <div className="eyebrow">Reading list</div>
          <h1 id="wl-title" className="m-0 text-[27px] font-extrabold leading-tight tracking-tight">{title}</h1>
        </div>
        <p className="m-0 hidden text-[12.5px] text-ink-3 md:block">
          <kbd>/</kbd> find · <kbd>J</kbd> <kbd>K</kbd> move · <kbd>Enter</kbd> open
          {canClaim && <> · <kbd>A</kbd> claim</>}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-3" role="group" aria-label="Filters">
        <SearchField
          aria-label="Find a patient, patient ID or accession number"
          defaultValue={search.q ?? ''}
          onSubmit={(v) => set({ q: v.trim() || undefined })}
          onClear={() => set({ q: undefined })}
          className="flex min-w-[220px] max-w-[380px] flex-1 items-center gap-2 rounded-[9px] border border-line-2 bg-surface px-2.5 py-1.5 text-ink-3 focus-within:border-blue"
        >
          <Search aria-hidden size={16} />
          <Input
            ref={searchInput}
            placeholder="Name, patient ID or accession, then Enter"
            className="min-w-0 flex-1 border-0 bg-transparent text-[14px] text-ink outline-none placeholder:text-ink-3 [&::-webkit-search-cancel-button]:hidden"
          />
          <Button className="rounded p-0.5 text-ink-3 hover:text-ink data-[empty]:hidden" aria-label="Clear the search">
            <X aria-hidden size={15} />
          </Button>
        </SearchField>

        <ToggleButtonGroup
          aria-label="Kind of study"
          selectionMode="multiple"
          selectedKeys={new Set(groups)}
          onSelectionChange={(keys) => set({ mod: GROUP_KEYS.filter((k) => keys.has(k)).join(',') || undefined })}
          className="flex flex-wrap gap-1.5"
        >
          {GROUP_KEYS.map((k: ModalityGroup) => (
            <ToggleButton
              key={k}
              id={k}
              className="rounded-full border border-line-2 bg-surface px-2.5 py-[3px] font-display text-[12px] font-bold text-ink-2 outline-none data-[focus-visible]:outline-2 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--focus)] data-[selected]:border-ink data-[selected]:bg-ink data-[selected]:text-bg"
            >
              {MODALITY_GROUPS[k].label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>

        {canClaim && (
          <ToggleButton
            isSelected={search.mine === '1'}
            onChange={(on) => set({ mine: on ? '1' : undefined })}
            className="rounded-full border border-line-2 bg-surface px-2.5 py-[3px] font-display text-[12px] font-bold text-ink-2 outline-none data-[focus-visible]:outline-2 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--focus)] data-[selected]:border-accent data-[selected]:bg-accent data-[selected]:text-on-accent"
          >
            Claimed by me
          </ToggleButton>
        )}

        <ToggleButtonGroup
          aria-label="How far back"
          selectionMode="single"
          disallowEmptySelection
          selectedKeys={new Set([range])}
          onSelectionChange={(keys) => {
            const [r] = [...keys];
            if (r) set({ range: r as WorklistSearch['range'] });
          }}
          className="flex overflow-hidden rounded-[9px] border border-line-2"
        >
          {(Object.keys(RANGE_LABELS) as (keyof typeof RANGE_LABELS)[]).map((r) => (
            <ToggleButton
              key={r}
              id={r}
              className="border-l border-line-2 bg-surface px-3 py-1 text-[13px] font-semibold text-ink-2 outline-none first:border-l-0 data-[focus-visible]:outline-2 data-[focus-visible]:-outline-offset-2 data-[focus-visible]:outline-[var(--focus)] data-[selected]:bg-accent data-[selected]:text-on-accent"
            >
              {RANGE_LABELS[r]}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      </div>

      <div role="status" aria-live="polite" className="min-h-0 empty:hidden">
        {notice && (
          <div className="inline-block rounded-lg border border-line bg-surface px-3 py-1.5 text-[13.5px] text-ink-2">{notice}</div>
        )}
      </div>

      {signedOut ? (
        <Notice title="Your session has ended." action={<a className="font-semibold text-accent-ink underline" href="/pmc/">Sign in again</a>}>
          Sign in again to see the worklist.
        </Notice>
      ) : studies.isError ? (
        <Notice
          title="The worklist could not be loaded."
          action={<Button className="inline-flex items-center gap-1.5 rounded-lg border border-line-2 bg-surface px-3 py-1.5 text-[13px] font-semibold" onPress={() => void studies.refetch()}><RotateCcw aria-hidden size={14} />Try again</Button>}
        >
          The imaging engine did not answer. If this keeps happening, call ICT.
        </Notice>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-line bg-surface">
          <Table
            ref={table}
            aria-label={title}
            aria-busy={studies.isFetching}
            className="wl"
            selectionMode="single"
            selectionBehavior="replace"
            selectedKeys={selected}
            onSelectionChange={setSelected}
            onRowAction={(key: Key) => {
              const s = byId.get(String(key));
              if (s) openViewer(s);
            }}
            sortDescriptor={sortDescriptor}
            onSortChange={onSortChange}
          >
            <TableHeader>
              <Column id="time" allowsSorting>Taken</Column>
              <Column id="patient" isRowHeader allowsSorting>Patient</Column>
              <Column id="study">Study</Column>
              <Column id="accession" allowsSorting>Accession</Column>
              <Column id="images">Images</Column>
              <Column id="state">State</Column>
              <Column id="reader">Reader</Column>
              <Column id="open"><span className="sr-only">Open</span></Column>
            </TableHeader>
            <TableBody
              items={rows}
              dependencies={[now]}
              renderEmptyState={() => (
                <div className="px-4 py-10 text-center text-ink-2">
                  {studies.isPending ? 'Loading the worklist…' : 'No study matches these filters.'}
                </div>
              )}
            >
              {(s) => (
                <StudyRow
                  study={s}
                  now={now}
                  me={me.data?.email}
                  canClaim={canClaim}
                  onClaim={() => toggleClaim.mutate(s)}
                />
              )}
            </TableBody>
          </Table>
          {(studies.hasNextPage || cut) && (
            <div className="flex items-center justify-center gap-3 border-t border-line px-4 py-3 text-[13px] text-ink-2">
              {cut ? (
                <span>Showing the first {rows.length} matches. Make the search more exact to see the rest.</span>
              ) : (
                <Button
                  className="rounded-lg border border-line-2 bg-surface px-3 py-1.5 font-semibold text-ink data-[pressed]:bg-surface-2"
                  isDisabled={studies.isFetchingNextPage}
                  onPress={() => void studies.fetchNextPage()}
                >
                  {studies.isFetchingNextPage ? 'Loading…' : 'Show more'}
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function StudyRow({ study: s, now, me, canClaim, onClaim }: {
  study: Study; now: number; me: string | undefined; canClaim: boolean; onClaim: () => void;
}) {
  const moment = studyMoment(s.studyDate, s.studyTime);
  const mine = s.claim !== null && s.claim.reader === me;
  const patient = personName(s.patientName);
  const claimButton = 'rounded-md border border-line-2 px-2 py-0.5 text-[12.5px] font-semibold text-ink-2 outline-none hover:bg-surface-2 data-[focus-visible]:outline-2 data-[focus-visible]:outline-[var(--focus)]';
  return (
    <Row id={s.id} textValue={personName(s.patientName)}>
      <Cell>
        <div className="whitespace-nowrap font-semibold tabular-nums">{ago(moment, now) || '—'}</div>
        <div className="whitespace-nowrap text-[12.5px] text-ink-3 tabular-nums">{when(moment, Boolean(s.studyTime))}</div>
      </Cell>
      <Cell>
        <div className="font-semibold md:whitespace-nowrap">{personName(s.patientName)}</div>
        <div className="text-[12.5px] text-ink-3 [overflow-wrap:anywhere] md:whitespace-nowrap">
          <span className="font-mono">{s.patientId || 'No ID'}</span>
          {sexAge(s.patientSex, s.patientBirthDate, now) && <> · {sexAge(s.patientSex, s.patientBirthDate, now)}</>}
        </div>
      </Cell>
      <Cell>
        <div className="flex flex-wrap items-center gap-1.5">
          {s.modalities.map((m) => (
            <span key={m} className={`pill chip-${['XA', 'RF', 'CT', 'CR', 'DX', 'MR', 'US'].includes(m) ? m : 'other'}`}>{m}</span>
          ))}
          <span className="text-ink-2">{s.description || 'No description'}</span>
        </div>
      </Cell>
      <Cell><span className="font-mono text-[13px]">{s.accession || '—'}</span></Cell>
      <Cell><span className="tabular-nums">{s.instances}</span></Cell>
      <Cell>
        {s.stable
          ? <span className="pill bg-ok-soft text-ok">Complete</span>
          : <span className="pill bg-warn-soft text-warn-ink">Arriving</span>}
      </Cell>
      <Cell>
        <div className="flex items-center gap-2 whitespace-nowrap">
          {mine ? (
            <span className="pill bg-accent-soft text-accent-ink">You</span>
          ) : s.claim ? (
            <span className="text-[13px] text-ink-2">{s.claim.readerName}</span>
          ) : !canClaim ? (
            <span className="text-ink-3">—</span>
          ) : null}
          {canClaim && (!s.claim || mine) && (
            <Button className={claimButton} onPress={onClaim} aria-label={`${mine ? 'Release' : 'Claim'} ${patient}`}>
              {mine ? 'Release' : 'Claim'}
            </Button>
          )}
        </div>
      </Cell>
      <Cell>
        <Link
          href={viewerUrl(s)}
          onPress={() => markOpened(s.studyUid)}
          target={VIEWER_WINDOW}
          aria-label={`Open ${personName(s.patientName)}, ${s.description || 'study'}, in the viewer`}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[13px] font-semibold text-accent-ink outline-none hover:bg-accent-soft data-[focus-visible]:outline-2 data-[focus-visible]:outline-[var(--focus)]"
        >
          Open <ExternalLink aria-hidden size={13} />
        </Link>
      </Cell>
    </Row>
  );
}

function Notice({ title, children, action }: { title: string; children: ReactNode; action: ReactNode }) {
  return (
    <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface px-4 py-4">
      <div>
        <div className="font-display font-bold">{title}</div>
        <div className="text-[14px] text-ink-2">{children}</div>
      </div>
      {action}
    </div>
  );
}
