// The worklist: every study a person may see, newest first, filtered in the
// URL so any view is a link. Enter or a double-click opens the study in the
// viewer, in one named window that stays on the second screen. A selected
// study is previewed beside the list.
//
// It must never lag (Dada, 25 Sep): only the rows on screen are in the page
// (a virtualized table), the table re-renders only when what it shows
// changes, the clock in each row ticks without re-rendering the row, a
// filter keeps the rows on screen until the new ones arrive, and the preview
// follows the keyboard once it settles.
import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearch } from '@tanstack/react-router';
import { ExternalLink, RotateCcw, Rows3, Rows4, Search, X } from 'lucide-react';
import {
  memo, useCallback, useDeferredValue, useEffect, useMemo, useRef, useState, useSyncExternalStore,
  type ReactNode, type RefObject,
} from 'react';
import {
  Button, Cell, Column, Input, Row, SearchField, Table, TableBody, TableHeader, TableLayout,
  ToggleButton, ToggleButtonGroup, Virtualizer, type Key, type Selection, type SortDescriptor,
} from 'react-aria-components';
import {
  GROUP_KEYS, MODALITY_GROUPS, READERS, modalityGroups, type ModalityGroup, type Study, type WorklistSearch,
} from '../shared/api.ts';
import {
  SignedOut, claimStudy, fetchMe, fetchStudies, markOpened, markRead, markUnread, releaseStudy, type Outcome,
} from './api.ts';
import { ago, personName, sexAge, studyMoment, when } from './format.ts';
import { VIEWER_WINDOW, openViewer, thumbnailUrl, viewerUrl } from './links.ts';
import { StudyPane, readingState } from './StudyPane.tsx';
import { Thumb } from './Thumb.tsx';

const PAGE = 50;
// An unread study that has waited this long is shown as waiting (Care Orange
// on its "ago"): INFERRED thresholds, for Dada to set (README, Open).
const WAITING_MS = 2 * 3_600_000;
const WAITING_LONG_MS = 8 * 3_600_000;
// A claim or a read, made or undone, and (when made) whether it went through.
type Change = { did: 'undo'; study: Study } | { did: 'do'; study: Study; result: Outcome };
const RANGE_LABELS = { today: 'Today', '3d': '3 days', '7d': '7 days', '30d': '30 days', all: 'All' } as const;
const COLUMN_SORT = { time: 'time', patient: 'patient', accession: 'accession' } as const;
const ROW = '.wl-body [role="row"]';

// One clock for every row's "8 min": it ticks every 30 s, and only the small
// pieces that show it re-render, never the rows.
const clock = { now: Date.now(), listeners: new Set<() => void>() };
setInterval(() => {
  clock.now = Date.now();
  for (const tell of clock.listeners) tell();
}, 30_000);
const useNow = () => useSyncExternalStore((tell) => {
  clock.listeners.add(tell);
  return () => {
    clock.listeners.delete(tell);
  };
}, () => clock.now);

function useMediaQuery(query: string): boolean {
  const mq = useMemo(() => matchMedia(query), [query]);
  return useSyncExternalStore((tell) => {
    mq.addEventListener('change', tell);
    return () => mq.removeEventListener('change', tell);
  }, () => mq.matches);
}

// Comfortable rows carry a small first image; compact rows do not, and sit
// closer. The choice stays in this browser.
type Density = 'comfortable' | 'compact';
function useDensity(): [Density, () => void] {
  const [density, setDensity] = useState<Density>(() => {
    try {
      return localStorage.getItem('pmc-density') === 'compact' ? 'compact' : 'comfortable';
    } catch {
      return 'comfortable';
    }
  });
  const toggle = () => {
    const next: Density = density === 'compact' ? 'comfortable' : 'compact';
    setDensity(next);
    try {
      localStorage.setItem('pmc-density', next);
    } catch {
      // a browser that keeps nothing still gets it for this visit
    }
  };
  return [density, toggle];
}

// A value that settles: holding J moves the selection every few milliseconds,
// and the preview follows only once it stops.
function useSettled<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return settled;
}

export function Worklist() {
  const search = useSearch({ from: '/' });
  const navigate = useNavigate({ from: '/' });
  const set = (patch: Partial<WorklistSearch>) =>
    void navigate({ search: (prev) => ({ ...prev, ...patch }), replace: true });
  const setRef = useRef(set);
  setRef.current = set;

  const me = useQuery({ queryKey: ['me'], queryFn: ({ signal }) => fetchMe(signal), staleTime: 60_000 });
  const referrerOnly = me.data?.roles.length === 1 && me.data.roles[0] === 'pmc-referrer';
  const canRead = me.data?.roles.some((r) => READERS.includes(r)) ?? false;
  const client = useQueryClient();
  const [notice, setNotice] = useState<string>();
  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(undefined), 6_000);
    return () => clearTimeout(t);
  }, [notice]);
  const changed = () => void client.invalidateQueries({ queryKey: ['studies'] });

  const toggleClaim = useMutation({
    mutationFn: async (s: Study): Promise<Change> => {
      if (s.claim?.reader === me.data?.username) {
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
      if (s.read?.reader === me.data?.username) {
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

  const range = search.range ?? '7d';
  const sort = search.sort ?? 'time';
  const groups = modalityGroups(search.mod);
  const params = {
    q: search.q, mod: groups.join(',') || undefined, range, sort, dir: search.dir, mine: search.mine, unread: search.unread,
  };

  // While the filters change, the rows already on screen stay until the new
  // ones arrive: no empty list, no "loading" flash.
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
  const byIdRef = useRef(byId);
  byIdRef.current = byId;
  const cut = studies.data?.pages.some((p) => p.more && p.sortedBy === 'page') ?? false;
  const total = studies.data?.pages[0]?.total;
  // The rows are drawn at a lower priority than a keystroke or a click.
  const shown = useDeferredValue(rows);
  // The first rows of a visit rise in one after another; after that, a row
  // that scrolls or arrives into view simply fades in.
  const [fresh, setFresh] = useState(true);
  const arrived = rows.length > 0;
  useEffect(() => {
    if (!arrived) return;
    const t = setTimeout(() => setFresh(false), 1_200);
    return () => clearTimeout(t);
  }, [arrived]);

  const [selected, setSelected] = useState<Selection>(new Set());
  const selectedId = selected === 'all' ? undefined : [...selected][0];
  const selectedStudy = selectedId === undefined ? undefined : byId.get(String(selectedId));
  const previewed = useSettled(selectedStudy, 120);
  const now = useNow();
  const [density, toggleDensity] = useDensity();
  // A phone shows three columns and few rows: the plain table. Anything wider
  // keeps only the rows on screen in the page.
  const virtual = useMediaQuery('(min-width: 721px)');
  const searchInput = useRef<HTMLInputElement>(null);
  const table = useRef<HTMLTableElement>(null);

  // "a" claims or releases, "r" marks read or unread, the study the keyboard is on.
  const actions = useRef({ claim: toggleClaim, read: toggleRead, canRead });
  actions.current = { claim: toggleClaim, read: toggleRead, canRead };
  const onClaim = useCallback((s: Study) => {
    if (!actions.current.claim.isPending) actions.current.claim.mutate(s);
  }, []);
  const onRead = useCallback((s: Study) => {
    if (!actions.current.read.isPending) actions.current.read.mutate(s);
  }, []);
  const onOpen = useCallback((key: Key) => {
    const s = byIdRef.current.get(String(key));
    if (s) openViewer(s);
  }, []);
  const onSortChange = useCallback((d: SortDescriptor) => setRef.current({
    sort: COLUMN_SORT[d.column as keyof typeof COLUMN_SORT] ?? 'time', dir: d.direction === 'ascending' ? 'asc' : 'desc',
  }), []);

  // "/" finds; j and k move, and select, so the preview follows; a claims;
  // r marks read; Escape closes the preview (or leaves the search box).
  useEffect(() => {
    const focusedRow = () => (document.activeElement as HTMLElement | null)?.closest<HTMLElement>(ROW) ?? null;
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement;
      if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === '/') {
        e.preventDefault();
        searchInput.current?.focus();
      } else if (e.key === 'j' || e.key === 'k') {
        e.preventDefault();
        const from = focusedRow();
        if (from && table.current?.contains(from)) {
          // The table's own arrow keys: they move focus to the next row, scroll
          // it into view, and select it (selection follows the keyboard).
          from.dispatchEvent(new KeyboardEvent('keydown', {
            key: e.key === 'j' ? 'ArrowDown' : 'ArrowUp', bubbles: true, cancelable: true,
          }));
        } else {
          table.current?.querySelector<HTMLElement>(ROW)?.focus();
        }
        const key = focusedRow()?.dataset.key;
        if (key) setSelected(new Set([key]));
      } else if (e.key === 'a' || e.key === 'r') {
        const id = focusedRow()?.dataset.key;
        const s = id ? byIdRef.current.get(id) : undefined;
        if (s && actions.current.canRead) {
          e.preventDefault();
          if (e.key === 'a') onClaim(s);
          else onRead(s);
        }
      } else if (e.key === 'Escape') {
        setSelected(new Set());
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClaim, onRead]);

  const sortDescriptor: SortDescriptor = useMemo(() => ({
    column: sort,
    direction: (search.dir ?? (sort === 'time' ? 'desc' : 'asc')) === 'asc' ? 'ascending' : 'descending',
  }), [sort, search.dir]);

  const title = referrerOnly ? 'Studies shared with you' : 'PMC imaging studies';
  const signedOut = studies.error instanceof SignedOut || me.error instanceof SignedOut;
  const chipClass = 'rounded-full border border-line-2 bg-surface px-2.5 py-[3px] font-display text-[12px] font-bold text-ink-2 outline-none data-[focus-visible]:outline-2 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--focus)] data-[selected]:border-ink data-[selected]:bg-ink data-[selected]:text-bg';
  const filterClass = 'rounded-full border border-line-2 bg-surface px-2.5 py-[3px] font-display text-[12px] font-bold text-ink-2 outline-none data-[focus-visible]:outline-2 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--focus)] data-[selected]:border-accent data-[selected]:bg-accent data-[selected]:text-on-accent';

  return (
    <section aria-labelledby="wl-title" className="flex min-h-0 flex-1 flex-col gap-4 px-4 py-5 md:px-6">
      <div className="enter flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div>
          <div className="eyebrow">Reading list</div>
          <h1 id="wl-title" className="m-0 text-[27px] font-extrabold leading-tight tracking-tight">{title}</h1>
        </div>
        <div className="flex flex-col items-end gap-1">
          <p className="m-0 hidden text-[12.5px] text-ink-3 md:block">
            <kbd>/</kbd> find · <kbd>J</kbd> <kbd>K</kbd> move · <kbd>Enter</kbd> open
            {canRead && <> · <kbd>A</kbd> claim · <kbd>R</kbd> read</>}
          </p>
          <p className="m-0 min-h-[18px] text-[13px] text-ink-2 tabular-nums" data-testid="total">
            {total !== undefined
              ? `${total.toLocaleString('en-PH')} ${total === 1 ? 'study' : 'studies'}${search.unread ? ', unread ones shown' : ''}`
              : ''}
          </p>
        </div>
      </div>

      <div className="enter enter-1 flex flex-wrap items-center gap-x-4 gap-y-3" role="group" aria-label="Filters">
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
            <ToggleButton key={k} id={k} className={chipClass}>{MODALITY_GROUPS[k].label}</ToggleButton>
          ))}
        </ToggleButtonGroup>

        <div className="flex flex-wrap gap-1.5">
          <ToggleButton isSelected={search.unread === '1'} onChange={(on) => set({ unread: on ? '1' : undefined })} className={filterClass}>
            Unread
          </ToggleButton>
          {canRead && (
            <ToggleButton isSelected={search.mine === '1'} onChange={(on) => set({ mine: on ? '1' : undefined })} className={filterClass}>
              Claimed by me
            </ToggleButton>
          )}
        </div>

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

        <Button
          onPress={toggleDensity}
          aria-label={density === 'compact' ? 'Comfortable rows' : 'Compact rows'}
          className="ml-auto rounded-lg border border-line-2 bg-surface p-1.5 text-ink-2 outline-none hover:text-ink data-[focus-visible]:outline-2 data-[focus-visible]:outline-[var(--focus)]"
        >
          {density === 'compact' ? <Rows3 aria-hidden size={16} /> : <Rows4 aria-hidden size={16} />}
        </Button>
      </div>

      <div role="status" aria-live="polite" className="min-h-0 empty:hidden">
        {notice && (
          <div key={notice} className="notice inline-block rounded-lg border border-line bg-surface px-3 py-1.5 text-[13.5px] text-ink-2 shadow-[var(--shadow-2)]">{notice}</div>
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
        <div className="flex min-h-0 flex-1 gap-4">
          <div
            aria-busy={studies.isFetching}
            className={`enter enter-2 flex min-h-0 min-w-0 flex-1 flex-col rounded-xl border border-line bg-surface shadow-[var(--shadow-2)] ${virtual ? 'overflow-hidden' : 'overflow-auto'} ${fresh ? 'wl-fresh' : ''}`}
          >
            <StudyTable
              tableRef={table}
              title={title}
              rows={shown}
              loading={studies.isPending}
              selected={selected}
              onSelectionChange={setSelected}
              onOpen={onOpen}
              sortDescriptor={sortDescriptor}
              onSortChange={onSortChange}
              density={density}
              virtual={virtual}
              canRead={canRead}
              me={me.data?.username}
              onClaim={onClaim}
              onRead={onRead}
            />
            {(studies.hasNextPage || cut) && (
              <div className="flex shrink-0 items-center justify-center gap-3 border-t border-line px-4 py-3 text-[13px] text-ink-2">
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
          {previewed && (
            <StudyPane
              study={byId.get(previewed.id) ?? previewed}
              now={now}
              me={me.data?.username}
              canRead={canRead}
              onClaim={onClaim}
              onRead={onRead}
              onClose={() => setSelected(new Set())}
            />
          )}
        </div>
      )}
    </section>
  );
}

// The table, apart from the page: it re-renders only when what it shows
// changes, never because the page fetched, ticked or noticed something.
interface TableProps {
  tableRef: RefObject<HTMLTableElement | null>;
  title: string;
  rows: Study[];
  loading: boolean;
  selected: Selection;
  onSelectionChange: (s: Selection) => void;
  onOpen: (key: Key) => void;
  sortDescriptor: SortDescriptor;
  onSortChange: (d: SortDescriptor) => void;
  density: Density;
  virtual: boolean;
  canRead: boolean;
  me: string | undefined;
  onClaim: (s: Study) => void;
  onRead: (s: Study) => void;
}

const StudyTable = memo(function StudyTable(p: TableProps) {
  // Column widths matter only to the virtualized table, which lays its rows
  // out itself; the plain table (a phone) sizes its columns as tables do.
  const width = (defaultWidth: number | `${number}fr`, minWidth: number) => (p.virtual ? { defaultWidth, minWidth } : {});
  const table = (
    <Table
      ref={p.tableRef}
      aria-label={p.title}
      className={p.virtual ? 'wl wl-virtual' : 'wl'}
      data-density={p.density}
      selectionMode="single"
      selectionBehavior="replace"
      selectedKeys={p.selected}
      onSelectionChange={p.onSelectionChange}
      onRowAction={p.onOpen}
      sortDescriptor={p.sortDescriptor}
      onSortChange={p.onSortChange}
    >
      <TableHeader>
        <Column id="time" allowsSorting {...width(110, 96)}>Taken</Column>
        <Column id="patient" isRowHeader allowsSorting {...width('2fr', 200)}>Patient</Column>
        <Column id="study" {...width('3fr', 180)}>Study</Column>
        <Column id="accession" allowsSorting {...width(130, 104)}>Accession</Column>
        <Column id="images" {...width(72, 60)}>Images</Column>
        <Column id="state" {...width(96, 84)}>State</Column>
        <Column id="reader" {...width(210, 190)}>Reader</Column>
        <Column id="open" {...width(84, 72)}><span className="sr-only">Open</span></Column>
      </TableHeader>
      <TableBody
        className="wl-body"
        items={p.rows}
        dependencies={[p.density, p.canRead, p.me]}
        renderEmptyState={() => (p.loading ? <Skeleton /> : <Empty />)}
      >
        {(s) => (
          <StudyRow
            study={s}
            me={p.me}
            canRead={p.canRead}
            thumbnails={p.density === 'comfortable'}
            onClaim={p.onClaim}
            onRead={p.onRead}
          />
        )}
      </TableBody>
    </Table>
  );
  if (!p.virtual) return table;
  // Rows are a fixed height (the cells truncate rather than wrap), so the
  // layout never measures them: no layout passes on the main thread.
  return (
    <Virtualizer layout={TableLayout} layoutOptions={{ rowHeight: p.density === 'compact' ? 52 : 64, headingHeight: 36 }}>
      {table}
    </Virtualizer>
  );
});

// "8 min", and, for a study nobody has taken up, how long it has waited: past
// two hours in Care Orange, past eight in bold as well.
function Ago({ moment, waiting }: { moment: number | undefined; waiting: boolean }) {
  const now = useNow();
  const waited = waiting && moment !== undefined ? now - moment : 0;
  const tone = waited > WAITING_LONG_MS ? 'text-orange-ink font-bold' : waited > WAITING_MS ? 'text-orange-ink' : '';
  const title = waited > WAITING_MS ? `Waiting to be read for ${ago(moment, now)}` : undefined;
  return <span className={tone} title={title}>{ago(moment, now) || '—'}</span>;
}

// Eight quiet rows that shimmer while the first page is on its way.
function Skeleton() {
  return (
    <div className="skeleton" aria-label="Loading the worklist" role="status">
      {Array.from({ length: 8 }, (_, i) => (
        <div key={i} className="skel-row" style={{ animationDelay: `${i * 40}ms` }}>
          <span className="skel skel-thumb" />
          <span className="skel" style={{ width: '18%' }} />
          <span className="skel" style={{ width: '34%' }} />
          <span className="skel" style={{ width: '10%' }} />
          <span className="skel" style={{ width: '8%' }} />
        </div>
      ))}
    </div>
  );
}

function Empty() {
  return (
    <div className="empty" role="status">
      <svg className="empty-art" viewBox="0 0 96 64" width="96" height="64" aria-hidden>
        <rect x="8" y="14" width="80" height="42" rx="8" fill="none" stroke="currentColor" strokeWidth="2" />
        <path d="M8 36h22l6 8h24l6-8h22" fill="none" stroke="currentColor" strokeWidth="2" />
        <path d="M36 8l12 12 22-16" fill="none" stroke="var(--green)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div className="font-display text-[15px] font-bold">Nothing to read here.</div>
      <div className="text-[13px] text-ink-3">No study matches these filters.</div>
    </div>
  );
}

// A plain button inside a row: the row's own keys and presses must not fire
// for it (Enter on "Claim" would otherwise also open the study).
function RowButton({ label, onPress, children }: { label: string; onPress: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      className="rowbtn"
      onClick={(e) => {
        e.stopPropagation();
        onPress();
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') e.stopPropagation();
      }}
    >
      {children}
    </button>
  );
}

function StudyRow({ study: s, me, canRead, thumbnails, onClaim, onRead }: {
  study: Study; me: string | undefined; canRead: boolean; thumbnails: boolean;
  onClaim: (s: Study) => void; onRead: (s: Study) => void;
}) {
  const moment = studyMoment(s.studyDate, s.studyTime);
  const mine = s.claim !== null && s.claim.reader === me;
  const patient = personName(s.patientName);
  const state = readingState(s, me);
  const age = sexAge(s.patientSex, s.patientBirthDate, clock.now);
  return (
    <Row id={s.id} textValue={patient}>
      <Cell>
        <div>
          <div className="whitespace-nowrap font-semibold tabular-nums">
            <Ago moment={moment} waiting={s.stable && !s.read && !s.claim} />
          </div>
          <div className="whitespace-nowrap text-[12.5px] text-ink-3 tabular-nums">{when(moment, Boolean(s.studyTime))}</div>
        </div>
      </Cell>
      <Cell>
        <div className="flex min-w-0 items-center gap-2.5">
          {thumbnails && <Thumb src={thumbnailUrl(s.studyUid)} />}
          <div className="min-w-0">
            <div className="truncate font-semibold">{patient}</div>
            <div className="truncate text-[12.5px] text-ink-3">
              <span className="font-mono">{s.patientId || 'No ID'}</span>
              {age && <> · {age}</>}
            </div>
          </div>
        </div>
      </Cell>
      <Cell>
        <div className="flex min-w-0 items-center gap-1.5">
          {s.modalities.map((m) => (
            <span key={m} className={`pill chip-${['XA', 'RF', 'CT', 'CR', 'DX', 'MR', 'US'].includes(m) ? m : 'other'}`}>{m}</span>
          ))}
          <span className="truncate text-ink-2">{s.description || 'No description'}</span>
        </div>
      </Cell>
      <Cell><span className="font-mono text-[13px]">{s.accession || '—'}</span></Cell>
      <Cell><span className="tabular-nums">{s.instances}</span></Cell>
      <Cell><span className={`pill ${state.tone}`}>{state.label}</span></Cell>
      <Cell>
        <div className="flex items-center gap-2 whitespace-nowrap">
          {state.who === 'You' ? (
            <span className="pill bg-accent-soft text-accent-ink">You</span>
          ) : state.who ? (
            <span className="truncate text-[13px] text-ink-2">{state.who}</span>
          ) : !canRead ? (
            <span className="text-ink-3">—</span>
          ) : null}
          {canRead && !s.read && (!s.claim || mine) && (
            <>
              <RowButton label={`${mine ? 'Release' : 'Claim'} ${patient}`} onPress={() => onClaim(s)}>
                {mine ? 'Release' : 'Claim'}
              </RowButton>
              <RowButton label={`Mark ${patient} read`} onPress={() => onRead(s)}>Mark read</RowButton>
            </>
          )}
          {canRead && s.read?.reader === me && (
            <RowButton label={`Mark ${patient} unread`} onPress={() => onRead(s)}>Unread</RowButton>
          )}
        </div>
      </Cell>
      <Cell>
        <a
          href={viewerUrl(s)}
          target={VIEWER_WINDOW}
          onClick={(e) => {
            e.stopPropagation();
            markOpened(s.studyUid);
          }}
          aria-label={`Open ${patient}, ${s.description || 'study'}, in the viewer`}
          className="rowlink"
        >
          Open <ExternalLink aria-hidden size={13} />
        </a>
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
