// The reading room (M5.4): the list and the viewer together on one screen.
// A rail of studies on the left, the viewer on the right, and the next study
// already loading in a second, hidden viewer, so J shows it at once. The
// keyboard goes from the rail to the images (Enter) and back (Esc).
//
// The viewer is OHIF in an iframe of this same origin, so the front door's
// session and rules apply unchanged, and this page can hear its keys.
import { useNavigate, useSearch } from '@tanstack/react-router';
import { ArrowLeft, ChevronDown, ChevronUp, Search, X } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Input, Link, SearchField, ToggleButton, type Key, type Selection } from 'react-aria-components';
import type { RoomSearch, Study } from '../shared/api.ts';
import { SignedOut, markOpened } from './api.ts';
import { personName, studyMoment, when } from './format.ts';
import { listParams, useMe, useReadingActions, useStudies } from './reading.ts';
import { readingState } from './StudyPane.tsx';
import { Notice, ROW, StudyTable, chip, stepRow } from './StudyTable.tsx';

type Slot = 'a' | 'b';
interface Stage { a: string | null; b: string | null; front: Slot }
const other = (s: Slot): Slot => (s === 'a' ? 'b' : 'a');
const viewerSrc = (uid: string) => `/viewer?StudyInstanceUIDs=${encodeURIComponent(uid)}`;

export function ReadingRoom() {
  const search = useSearch({ from: '/read' });
  const navigate = useNavigate({ from: '/read' });
  const go = (patch: Partial<RoomSearch>) =>
    void navigate({ search: (prev) => ({ ...prev, ...patch }), replace: true });
  const goRef = useRef(go);
  goRef.current = go;

  const me = useMe();
  const { notice, onClaim, onRead, canRead } = useReadingActions(me.data);
  const { studies, rows, byId } = useStudies(listParams(search));
  const rowsRef = useRef(rows);
  rowsRef.current = rows;

  // The current study: the address's, or the first of the list.
  const currentUid = search.study ?? rows[0]?.studyUid;
  const index = rows.findIndex((s) => s.studyUid === currentUid);
  const current = index >= 0 ? rows[index] : undefined;
  const next = index >= 0 ? rows[index + 1] : undefined;
  const prev = index > 0 ? rows[index - 1] : undefined;
  const nextUid = next?.studyUid ?? null;

  // Two viewers: the front one shows the current study; the back one loads
  // the next. Moving on to a study the back viewer already holds swaps them,
  // and the viewer that was in front turns to the study after that.
  const [stage, setStage] = useState<Stage>({ a: currentUid ?? null, b: nextUid, front: 'a' });
  useEffect(() => {
    if (!currentUid) return;
    setStage((f) => {
      const back = other(f.front);
      if (f[back] === currentUid) return { ...f, front: back, [f.front]: nextUid };
      if (f[f.front] === currentUid) return f[back] === nextUid ? f : { ...f, [back]: nextUid };
      return { ...f, [f.front]: currentUid, [back]: nextUid };
    });
  }, [currentUid, nextUid]);
  useEffect(() => {
    if (currentUid) markOpened(currentUid);
  }, [currentUid]);

  const rail = useRef<HTMLTableElement>(null);
  const frames = useRef<Record<Slot, HTMLIFrameElement | null>>({ a: null, b: null });
  const searchInput = useRef<HTMLInputElement>(null);

  const show = useCallback((s: Study | undefined) => {
    if (s) goRef.current({ study: s.studyUid });
  }, []);
  const focusRail = useCallback(() => {
    const id = current?.id;
    const row = (id && rail.current?.querySelector<HTMLElement>(`${ROW}[data-key="${CSS.escape(id)}"]`))
      || rail.current?.querySelector<HTMLElement>(ROW);
    row?.focus();
  }, [current?.id]);
  const focusViewer = useCallback(() => {
    frames.current[stage.front]?.focus();
  }, [stage.front]);

  // The room's keys, on this page: j and k move (the rail's own arrow keys,
  // so the row scrolls into view), Enter and Space go to the images, a
  // claims, r marks read and moves on, / finds. Inside the viewer, its own
  // keys apply; only Esc (back to the rail), j and k (which OHIF does not
  // use; MEASURED from its hotkeys) are heard from there too.
  const latest = useRef({ current, next, prev, canRead, onClaim, onRead, focusRail, focusViewer, show });
  latest.current = { current, next, prev, canRead, onClaim, onRead, focusRail, focusViewer, show };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement;
      if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
      const L = latest.current;
      if (e.key === '/') {
        e.preventDefault();
        searchInput.current?.focus();
      } else if (e.key === 'j' || e.key === 'k') {
        e.preventDefault();
        const key = stepRow(rail.current, e.key === 'j' ? 'down' : 'up', L.current?.id);
        const s = key ? rowsRef.current.find((r) => r.id === key) : undefined;
        if (s && s.id !== L.current?.id) L.show(s);
      } else if (e.key === 'Enter' || e.key === ' ') {
        if ((e.target as HTMLElement | null)?.closest(ROW)) {
          e.preventDefault();
          e.stopPropagation();
          L.focusViewer();
        }
      } else if (e.key === 'a' && L.current && L.canRead) {
        e.preventDefault();
        L.onClaim(L.current);
      } else if (e.key === 'r' && L.current && L.canRead) {
        e.preventDefault();
        L.onRead(L.current);
        if (!L.current.read) L.show(L.next);
      }
    };
    // Before the table's own Enter (which would open a window): capture phase.
    document.addEventListener('keydown', onKey, true);
    return () => document.removeEventListener('keydown', onKey, true);
  }, []);

  // The viewer's document is this origin's: hear Esc, j and k from it.
  const onFrameLoad = useCallback((slot: Slot) => {
    const doc = frames.current[slot]?.contentDocument;
    if (!doc) return;
    doc.addEventListener('keydown', (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement;
      if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
      const L = latest.current;
      if (e.key === 'Escape') {
        e.preventDefault();
        L.focusRail();
      } else if (e.key === 'j') {
        e.preventDefault();
        L.show(L.next);
      } else if (e.key === 'k') {
        e.preventDefault();
        L.show(L.prev);
      }
    });
  }, []);

  const selected = useMemo<Selection>(() => new Set(current ? [current.id] : []), [current]);
  const onSelectionChange = useCallback((keys: Selection) => {
    const [key] = keys === 'all' ? [] : [...keys];
    const s = key === undefined ? undefined : byId.get(String(key));
    if (s) goRef.current({ study: s.studyUid });
  }, [byId]);
  const onOpen = useCallback((key: Key) => {
    const s = byId.get(String(key));
    if (s) {
      goRef.current({ study: s.studyUid });
      latest.current.focusViewer();
    }
  }, [byId]);

  const signedOut = studies.error instanceof SignedOut || me.error instanceof SignedOut;
  const state = current ? readingState(current, me.data?.username) : undefined;
  const moment = current ? studyMoment(current.studyDate, current.studyTime) : undefined;
  const filterClass = 'rounded-full border border-line-2 bg-surface px-2.5 py-[3px] font-display text-[12px] font-bold text-ink-2 outline-none data-[focus-visible]:outline-2 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--focus)] data-[selected]:border-accent data-[selected]:bg-accent data-[selected]:text-on-accent';
  const tool = 'inline-flex items-center gap-1 rounded-lg border border-line-2 bg-surface px-2.5 py-1 text-[13px] font-semibold text-ink outline-none hover:bg-surface-2 data-[focus-visible]:outline-2 data-[focus-visible]:outline-[var(--focus)] data-[disabled]:opacity-40';
  const listHref = `/pmc/?${new URLSearchParams(Object.fromEntries(Object.entries(search).filter(([k, v]) => k !== 'study' && v !== undefined).map(([k, v]) => [k, String(v)])))}`;

  return (
    <section aria-label="Reading room" className="room flex min-h-0 flex-1">
      <aside className="rail enter flex min-h-0 w-[340px] shrink-0 flex-col border-r border-line bg-surface">
        <div className="flex flex-col gap-2 border-b border-line px-3 py-2.5">
          <div className="flex items-center gap-2">
            <Link href={listHref} className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[13px] font-semibold text-accent-ink no-underline outline-none hover:bg-accent-soft data-[focus-visible]:outline-2 data-[focus-visible]:outline-[var(--focus)]">
              <ArrowLeft aria-hidden size={14} /> List
            </Link>
            <span className="eyebrow ml-auto">Reading room</span>
          </div>
          <SearchField
            aria-label="Find a patient, patient ID or accession number"
            defaultValue={search.q ?? ''}
            onSubmit={(v) => go({ q: v.trim() || undefined })}
            onClear={() => go({ q: undefined })}
            className="flex items-center gap-2 rounded-[9px] border border-line-2 bg-surface px-2.5 py-1 text-ink-3 focus-within:border-blue"
          >
            <Search aria-hidden size={15} />
            <Input ref={searchInput} placeholder="Find, then Enter" className="min-w-0 flex-1 border-0 bg-transparent text-[13.5px] text-ink outline-none placeholder:text-ink-3 [&::-webkit-search-cancel-button]:hidden" />
            <Button className="rounded p-0.5 text-ink-3 hover:text-ink data-[empty]:hidden" aria-label="Clear the search"><X aria-hidden size={14} /></Button>
          </SearchField>
          <div className="flex flex-wrap gap-1.5">
            <ToggleButton isSelected={search.unread === '1'} onChange={(on) => go({ unread: on ? '1' : undefined })} className={filterClass}>Unread</ToggleButton>
            {canRead && (
              <ToggleButton isSelected={search.mine === '1'} onChange={(on) => go({ mine: on ? '1' : undefined })} className={filterClass}>Claimed by me</ToggleButton>
            )}
          </div>
        </div>
        <div aria-busy={studies.isFetching} className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <StudyTable
            tableRef={rail}
            title="Studies to read"
            rows={rows}
            loading={studies.isPending}
            selected={selected}
            onSelectionChange={onSelectionChange}
            onOpen={onOpen}
            density="comfortable"
            virtual
            rail
            canRead={canRead}
            me={me.data?.username}
            onClaim={onClaim}
            onRead={onRead}
          />
        </div>
        <p className="m-0 border-t border-line px-3 py-2 text-[12px] text-ink-3">
          <kbd>J</kbd> <kbd>K</kbd> next, previous · <kbd>Enter</kbd> images · <kbd>Esc</kbd> back
          {canRead && <> · <kbd>A</kbd> claim · <kbd>R</kbd> read, next</>}
        </p>
      </aside>

      <div className="stage-col flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="toolbar flex items-center gap-3 border-b border-line bg-surface px-3 py-1.5">
          <div className="min-w-0 flex-1 truncate text-[13.5px]" data-testid="current">
            {current ? (
              <>
                <b>{personName(current.patientName)}</b>
                <span className="text-ink-3"> · </span>
                {current.modalities.map((m) => <span key={m} className={`${chip(m)} mr-1`}>{m}</span>)}
                <span className="text-ink-2">{current.description || 'No description'}</span>
                <span className="text-ink-3"> · {when(moment, Boolean(current.studyTime))}</span>
                {state && <span className={`pill ml-2 ${state.tone}`}>{state.label}{state.who ? `: ${state.who}` : ''}</span>}
              </>
            ) : (
              <span className="text-ink-3">{studies.isPending ? 'Loading…' : 'No study to read.'}</span>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <Button className={tool} isDisabled={!prev} onPress={() => show(prev)} aria-label="Previous study (K)"><ChevronUp aria-hidden size={14} />Previous</Button>
            <Button className={tool} isDisabled={!next} onPress={() => show(next)} aria-label="Next study (J)">Next<ChevronDown aria-hidden size={14} /></Button>
            {canRead && current && (
              <>
                <Button className={tool} onPress={() => onClaim(current)} aria-label={`${current.claim?.reader === me.data?.username ? 'Release' : 'Claim'} ${personName(current.patientName)}`}>
                  {current.claim?.reader === me.data?.username ? 'Release' : 'Claim'}
                </Button>
                <Button
                  className={tool}
                  onPress={() => {
                    onRead(current);
                    if (!current.read) show(next);
                  }}
                  aria-label={`Mark ${personName(current.patientName)} ${current.read ? 'unread' : 'read'}`}
                >
                  {current.read ? 'Unread' : 'Mark read'}
                </Button>
              </>
            )}
          </div>
        </div>
        <div role="status" aria-live="polite" className="empty:hidden">
          {notice && <div key={notice} className="notice mx-3 mt-2 inline-block rounded-lg border border-line bg-surface px-3 py-1.5 text-[13.5px] text-ink-2 shadow-[var(--shadow-2)]">{notice}</div>}
        </div>
        {signedOut ? (
          <div className="p-4">
            <Notice title="Your session has ended." action={<a className="font-semibold text-accent-ink underline" href="/pmc/">Sign in again</a>}>
              Sign in again to keep reading.
            </Notice>
          </div>
        ) : (
          <div className="stage relative min-h-0 flex-1 bg-black">
            {(['a', 'b'] as Slot[]).map((slot) => {
              const uid = stage[slot];
              const front = stage.front === slot;
              return (
                <iframe
                  key={slot}
                  ref={(el) => { frames.current[slot] = el; }}
                  title={front ? 'The images' : 'The next study, loading'}
                  data-front={front}
                  data-study={uid ?? ''}
                  src={uid ? viewerSrc(uid) : 'about:blank'}
                  onLoad={() => onFrameLoad(slot)}
                  className={`stage-frame absolute inset-0 h-full w-full border-0 ${front ? '' : 'stage-back'}`}
                  aria-hidden={!front}
                  tabIndex={front ? 0 : -1}
                />
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
