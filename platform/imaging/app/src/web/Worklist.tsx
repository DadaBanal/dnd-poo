// The worklist: every study a person may see, newest first, filtered in the
// URL so any view is a link. Enter or a double-click opens the study in the
// viewer, in one named window that stays on the second screen. A selected
// study is previewed beside the list; the reading room (ReadingRoom.tsx)
// holds the list and the viewer together on one screen.
import { Link as RouteLink, useNavigate, useSearch } from '@tanstack/react-router';
import { BookOpen, RotateCcw, Rows3, Rows4, Search, X } from 'lucide-react';
import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import {
  Button, Input, SearchField, ToggleButton, ToggleButtonGroup, type Key, type Selection, type SortDescriptor,
} from 'react-aria-components';
import { GROUP_KEYS, MODALITY_GROUPS, modalityGroups, type ModalityGroup, type RoomSearch, type WorklistSearch } from '../shared/api.ts';
import { SignedOut } from './api.ts';
import { openViewer } from './links.ts';
import { listParams, useMe, useReadingActions, useStudies } from './reading.ts';
import { StudyPane } from './StudyPane.tsx';
import { Notice, ROW, StudyTable, stepRow, useDensity, useMediaQuery, useNow } from './StudyTable.tsx';

const RANGE_LABELS = { today: 'Today', '3d': '3 days', '7d': '7 days', '30d': '30 days', all: 'All' } as const;
const COLUMN_SORT = { time: 'time', patient: 'patient', accession: 'accession' } as const;

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

  const me = useMe();
  const referrerOnly = me.data?.roles.length === 1 && me.data.roles[0] === 'pmc-referrer';
  const { notice, onClaim, onRead, canRead } = useReadingActions(me.data);
  const params = listParams(search);
  const { studies, rows, byId, cut, total } = useStudies(params);
  const byIdRef = useRef(byId);
  byIdRef.current = byId;
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
  const able = useRef(canRead);
  able.current = canRead;

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
        const key = stepRow(table.current, e.key === 'j' ? 'down' : 'up');
        if (key) setSelected(new Set([key]));
      } else if (e.key === 'a' || e.key === 'r') {
        const id = focusedRow()?.dataset.key;
        const s = id ? byIdRef.current.get(id) : undefined;
        if (s && able.current) {
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

  const sort = search.sort ?? 'time';
  const sortDescriptor: SortDescriptor = useMemo(() => ({
    column: sort,
    direction: (search.dir ?? (sort === 'time' ? 'desc' : 'asc')) === 'asc' ? 'ascending' : 'descending',
  }), [sort, search.dir]);
  const range = search.range ?? '7d';
  const groups = modalityGroups(search.mod);

  const title = referrerOnly ? 'Studies shared with you' : 'PMC imaging studies';
  const signedOut = studies.error instanceof SignedOut || me.error instanceof SignedOut;
  const chipClass = 'rounded-full border border-line-2 bg-surface px-2.5 py-[3px] font-display text-[12px] font-bold text-ink-2 outline-none data-[focus-visible]:outline-2 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--focus)] data-[selected]:border-ink data-[selected]:bg-ink data-[selected]:text-bg';
  const filterClass = 'rounded-full border border-line-2 bg-surface px-2.5 py-[3px] font-display text-[12px] font-bold text-ink-2 outline-none data-[focus-visible]:outline-2 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--focus)] data-[selected]:border-accent data-[selected]:bg-accent data-[selected]:text-on-accent';
  // The room's address: the same filters, and the selected study (a router
  // link: the room opens without a page load).
  const roomSearch: RoomSearch = { ...search, study: selectedStudy?.studyUid };

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

        <div className="ml-auto flex items-center gap-2">
          {virtual && (
            <RouteLink
              to="/read"
              search={roomSearch}
              className="inline-flex items-center gap-1.5 rounded-lg border border-line-2 bg-surface px-2.5 py-1.5 text-[13px] font-semibold text-ink no-underline outline-none hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-[var(--focus)]"
            >
              <BookOpen aria-hidden size={15} />
              Reading room
            </RouteLink>
          )}
          <Button
            onPress={toggleDensity}
            aria-label={density === 'compact' ? 'Comfortable rows' : 'Compact rows'}
            className="rounded-lg border border-line-2 bg-surface p-1.5 text-ink-2 outline-none hover:text-ink data-[focus-visible]:outline-2 data-[focus-visible]:outline-[var(--focus)]"
          >
            {density === 'compact' ? <Rows3 aria-hidden size={16} /> : <Rows4 aria-hidden size={16} />}
          </Button>
        </div>
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
