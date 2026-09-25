// The reading list's table, shared by the list page and the reading room's
// rail. It never lags (Dada, 25 Sep): only the rows on screen are in the page
// (a virtualized table with fixed row heights), it re-renders only when what
// it shows changes, and the clock in each row ticks without re-rendering the
// row. On a phone it is a plain table.
import { ExternalLink } from 'lucide-react';
import { memo, useMemo, useState, useSyncExternalStore, type ReactNode, type RefObject } from 'react';
import {
  Cell, Column, Row, Table, TableBody, TableHeader, TableLayout, Virtualizer,
  type Key, type Selection, type SortDescriptor,
} from 'react-aria-components';
import type { Study } from '../shared/api.ts';
import { markOpened } from './api.ts';
import { ago, personName, sexAge, studyMoment, when } from './format.ts';
import { VIEWER_WINDOW, thumbnailUrl, viewerUrl } from './links.ts';
import { readingState } from './StudyPane.tsx';
import { Thumb } from './Thumb.tsx';

export const ROW = '.wl-body [role="row"]';
// An unread study that has waited this long is shown as waiting (Care Orange
// on its "ago"): INFERRED thresholds, for Dada to set (README, Open).
const WAITING_MS = 2 * 3_600_000;
const WAITING_LONG_MS = 8 * 3_600_000;
// Every code the chips have a colour for (styles.css): the kinds of study
// PMC's machines make (shared/api.ts, MODALITY_GROUPS), and PET.
const CHIPS = ['XA', 'RF', 'CT', 'CR', 'DX', 'MR', 'US', 'MG', 'NM', 'PT', 'BMD', 'PX', 'IO', 'OP', 'OPT', 'OPV', 'OPM', 'ES', 'XC', 'RTIMAGE', 'RTDOSE', 'RTSTRUCT', 'RTPLAN', 'RTRECORD'];
export const chip = (m: string) => `pill chip-${CHIPS.includes(m) ? m : 'other'}`;

// One clock for every row's "8 min": it ticks every 30 s, and only the small
// pieces that show it re-render, never the rows.
export const clock = { now: Date.now(), listeners: new Set<() => void>() };
setInterval(() => {
  clock.now = Date.now();
  for (const tell of clock.listeners) tell();
}, 30_000);
export const useNow = () => useSyncExternalStore((tell) => {
  clock.listeners.add(tell);
  return () => {
    clock.listeners.delete(tell);
  };
}, () => clock.now);

export function useMediaQuery(query: string): boolean {
  const mq = useMemo(() => matchMedia(query), [query]);
  return useSyncExternalStore((tell) => {
    mq.addEventListener('change', tell);
    return () => mq.removeEventListener('change', tell);
  }, () => mq.matches);
}

// Comfortable rows carry a small first image; compact rows do not, and sit
// closer. The choice stays in this browser.
export type Density = 'comfortable' | 'compact';
export function useDensity(): [Density, () => void] {
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

// Move the keyboard one row down or up: from the row that has focus, or
// from `fromId`'s row, or onto the first. The neighbour is found among the
// rows on screen (in the virtualized table they sit in wrappers placed by
// top, and the DOM order is not promised) and focused directly, which also
// scrolls it into view; the table renders further rows as it scrolls.
// Returns the key of the row the keyboard is on afterwards, or undefined
// when there is no neighbour on screen (the end of the list, or its edge).
export function stepRow(root: HTMLElement | null, dir: 'down' | 'up', fromId?: string): string | undefined {
  if (!root) return undefined;
  const all = [...root.querySelectorAll<HTMLElement>(ROW)];
  if (!all.length) return undefined;
  const top = (el: HTMLElement) => parseFloat((el.parentElement as HTMLElement | null)?.style.top || '') || 0;
  const rows = root.classList.contains('wl-virtual') ? all.sort((a, b) => top(a) - top(b)) : all;
  const active = (document.activeElement as HTMLElement | null)?.closest<HTMLElement>(ROW);
  let base = active && root.contains(active) ? active : undefined;
  if (!base) {
    base = fromId ? rows.find((r) => r.dataset.key === fromId) : undefined;
    if (!base) {
      rows[0]?.focus();
      return rows[0]?.dataset.key;
    }
  }
  const target = rows[rows.indexOf(base) + (dir === 'down' ? 1 : -1)];
  if (!target) {
    base.scrollIntoView({ block: 'nearest' });
    return undefined;
  }
  target.focus();
  return target.dataset.key;
}

// The table, apart from the page: it re-renders only when what it shows
// changes, never because the page fetched, ticked or noticed something.
export interface TableProps {
  tableRef: RefObject<HTMLTableElement | null>;
  title: string;
  rows: Study[];
  loading: boolean;
  selected: Selection;
  onSelectionChange: (s: Selection) => void;
  onOpen: (key: Key) => void;
  sortDescriptor?: SortDescriptor;
  onSortChange?: (d: SortDescriptor) => void;
  density: Density;
  virtual: boolean;
  // The reading room's rail: one column, each study a small card.
  rail?: boolean;
  canRead: boolean;
  me: string | undefined;
  onClaim: (s: Study) => void;
  onRead: (s: Study) => void;
}

export const StudyTable = memo(function StudyTable(p: TableProps) {
  // Column widths matter only to the virtualized table, which lays its rows
  // out itself; the plain table (a phone) sizes its columns as tables do.
  const width = (defaultWidth: number | `${number}fr`, minWidth: number) => (p.virtual ? { defaultWidth, minWidth } : {});
  const table = (
    <Table
      ref={p.tableRef}
      aria-label={p.title}
      className={`wl ${p.virtual ? 'wl-virtual' : ''} ${p.rail ? 'wl-rail' : ''}`}
      data-density={p.density}
      selectionMode="single"
      selectionBehavior="replace"
      selectedKeys={p.selected}
      onSelectionChange={p.onSelectionChange}
      onRowAction={p.onOpen}
      sortDescriptor={p.sortDescriptor}
      onSortChange={p.onSortChange}
    >
      {p.rail ? (
        <TableHeader>
          <Column id="study" isRowHeader {...width('1fr', 200)}>Studies</Column>
        </TableHeader>
      ) : (
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
      )}
      <TableBody
        className="wl-body"
        items={p.rows}
        dependencies={[p.density, p.canRead, p.me, p.rail]}
        renderEmptyState={() => (p.loading ? <Skeleton /> : <Empty />)}
      >
        {(s) => (p.rail ? (
          <RailRow study={s} me={p.me} />
        ) : (
          <StudyRow
            study={s}
            me={p.me}
            canRead={p.canRead}
            thumbnails={p.density === 'comfortable'}
            onClaim={p.onClaim}
            onRead={p.onRead}
          />
        ))}
      </TableBody>
    </Table>
  );
  if (!p.virtual) return table;
  // Rows are a fixed height (the cells truncate rather than wrap), so the
  // layout never measures them: no layout passes on the main thread.
  const rowHeight = p.rail ? 68 : p.density === 'compact' ? 52 : 64;
  return (
    <Virtualizer layout={TableLayout} layoutOptions={{ rowHeight, headingHeight: p.rail ? 30 : 36 }}>
      {table}
    </Virtualizer>
  );
});

// "8 min", and, for a study nobody has taken up, how long it has waited: past
// two hours in Care Orange, past eight in bold as well.
export function Ago({ moment, waiting }: { moment: number | undefined; waiting: boolean }) {
  const now = useNow();
  const waited = waiting && moment !== undefined ? now - moment : 0;
  const tone = waited > WAITING_LONG_MS ? 'text-orange-ink font-bold' : waited > WAITING_MS ? 'text-orange-ink' : '';
  const title = waited > WAITING_MS ? `Waiting to be read for ${ago(moment, now)}` : undefined;
  return <span className={tone} title={title}>{ago(moment, now) || '—'}</span>;
}

// Eight quiet rows that shimmer while the first page is on its way.
export function Skeleton() {
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

export function Empty() {
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
export function RowButton({ label, onPress, children }: { label: string; onPress: () => void; children: ReactNode }) {
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
          {s.modalities.map((m) => <span key={m} className={chip(m)}>{m}</span>)}
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

// A study in the reading room's rail: its image, the patient, when, what,
// and its state, in one card.
function RailRow({ study: s, me }: { study: Study; me: string | undefined }) {
  const moment = studyMoment(s.studyDate, s.studyTime);
  const patient = personName(s.patientName);
  const state = readingState(s, me);
  return (
    <Row id={s.id} textValue={patient}>
      <Cell>
        <div className="flex min-w-0 flex-1 items-center gap-2.5" data-study={s.studyUid}>
          <Thumb src={thumbnailUrl(s.studyUid)} />
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-2">
              <span className="min-w-0 flex-1 truncate">
                <span className="font-semibold">{patient}</span>
                <span className="font-mono text-[11.5px] text-ink-3"> · {s.patientId || 'No ID'}</span>
              </span>
              <span className="shrink-0 text-[12px] text-ink-3 tabular-nums">
                <Ago moment={moment} waiting={s.stable && !s.read && !s.claim} />
              </span>
            </div>
            <div className="flex min-w-0 items-center gap-1.5 text-[12.5px] text-ink-2">
              {s.modalities.slice(0, 2).map((m) => <span key={m} className={chip(m)}>{m}</span>)}
              <span className="min-w-0 flex-1 truncate">{s.description || 'No description'}</span>
              <span className={`pill shrink-0 ${state.tone}`}>{state.label}</span>
            </div>
          </div>
        </div>
      </Cell>
    </Row>
  );
}

export function Notice({ title, children, action }: { title: string; children: ReactNode; action: ReactNode }) {
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
