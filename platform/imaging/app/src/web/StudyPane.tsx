// The preview pane: the selected study in full, beside the list. The header is
// drawn at once from the row the person is on; the series and the patient's
// earlier studies arrive from the server a moment later.
import { useQuery } from '@tanstack/react-query';
import { Columns2, ExternalLink, X } from 'lucide-react';
import { Button, Link } from 'react-aria-components';
import type { Series, Study } from '../shared/api.ts';
import { fetchStudy, markOpened } from './api.ts';
import { ago, personName, sexAge, studyMoment, when } from './format.ts';
import { VIEWER_WINDOW, compareUrl, seriesThumbnailUrl, thumbnailUrl, viewerUrl } from './links.ts';
import { Thumb } from './Thumb.tsx';

const chip = (m: string) => `pill chip-${['XA', 'RF', 'CT', 'CR', 'DX', 'MR', 'US'].includes(m) ? m : 'other'}`;
const button = 'inline-flex items-center gap-1.5 rounded-lg border border-line-2 bg-surface px-2.5 py-1 text-[13px] font-semibold text-ink outline-none hover:bg-surface-2 data-[focus-visible]:outline-2 data-[focus-visible]:outline-[var(--focus)]';
const primary = 'inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1 text-[13px] font-semibold text-on-accent no-underline outline-none hover:opacity-90 data-[focus-visible]:outline-2 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-[var(--focus)]';

// What the list knows of a study's reading state, in words.
export function readingState(s: Study, me: string | undefined): { label: string; who: string; tone: string } {
  if (!s.stable) return { label: 'Arriving', who: '', tone: 'bg-warn-soft text-warn-ink' };
  if (s.read) return { label: 'Read', who: s.read.reader === me ? 'You' : s.read.readerName, tone: 'bg-ok-soft text-ok' };
  if (s.claim) return { label: 'Claimed', who: s.claim.reader === me ? 'You' : s.claim.readerName, tone: 'bg-accent-soft text-accent-ink' };
  return { label: 'Unread', who: '', tone: 'bg-surface-3 text-ink-2' };
}

export function StudyPane({ study: s, now, me, canRead, onClaim, onRead, onClose }: {
  study: Study;
  now: number;
  me: string | undefined;
  canRead: boolean;
  onClaim: (s: Study) => void;
  onRead: (s: Study) => void;
  onClose: () => void;
}) {
  const detail = useQuery({
    queryKey: ['study', s.studyUid],
    queryFn: ({ signal }) => fetchStudy(s.studyUid, signal),
    staleTime: 30_000,
  });
  const moment = studyMoment(s.studyDate, s.studyTime);
  const state = readingState(s, me);
  const mine = s.claim?.reader === me;
  const patient = personName(s.patientName);

  return (
    <aside
      aria-label="Study preview"
      className="pane hidden w-[360px] shrink-0 flex-col gap-4 overflow-auto rounded-xl border border-line bg-surface p-4 shadow-[var(--shadow-2)] xl:flex"
    >
      <div key={s.studyUid} className="pane-body flex flex-col gap-4">
      <div className="flex items-start gap-3">
        <Thumb src={thumbnailUrl(s.studyUid, 192)} size={96} className="thumb-lg" />
        <div className="min-w-0 flex-1">
          <div className="eyebrow">Patient</div>
          <h2 className="m-0 text-[18px] font-extrabold leading-tight">{patient}</h2>
          <div className="text-[13px] text-ink-2 [overflow-wrap:anywhere]">
            <span className="font-mono">{s.patientId || 'No ID'}</span>
            {sexAge(s.patientSex, s.patientBirthDate, now) && <> · {sexAge(s.patientSex, s.patientBirthDate, now)}</>}
          </div>
        </div>
        <Button onPress={onClose} aria-label="Close the preview" className="rounded-md p-1 text-ink-3 outline-none hover:text-ink data-[focus-visible]:outline-2 data-[focus-visible]:outline-[var(--focus)]">
          <X aria-hidden size={16} />
        </Button>
      </div>

      <div className="flex flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-1.5">
          {s.modalities.map((m) => <span key={m} className={chip(m)}>{m}</span>)}
          <span className="font-semibold">{s.description || 'No description'}</span>
        </div>
        <div className="text-[13px] text-ink-2 tabular-nums">
          {when(moment, Boolean(s.studyTime))}{ago(moment, now) && <> · {ago(moment, now)} ago</>}
          {s.accession && <> · <span className="font-mono">{s.accession}</span></>}
          {' · '}{s.instances} {s.instances === 1 ? 'image' : 'images'}
        </div>
        <div className="flex items-center gap-2 text-[13px] text-ink-2">
          <span className={`pill ${state.tone}`}>{state.label}</span>
          {state.who && <span>{state.who}</span>}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Link href={viewerUrl(s)} target={VIEWER_WINDOW} onPress={() => markOpened(s.studyUid)} className={primary}>
          Open <ExternalLink aria-hidden size={13} />
        </Link>
        {canRead && !s.read && (!s.claim || mine) && (
          <>
            <Button className={button} onPress={() => onClaim(s)} aria-label={`${mine ? 'Release' : 'Claim'} ${patient}`}>
              {mine ? 'Release' : 'Claim'}
            </Button>
            <Button className={button} onPress={() => onRead(s)} aria-label={`Mark ${patient} read`}>Mark read</Button>
          </>
        )}
        {canRead && s.read?.reader === me && (
          <Button className={button} onPress={() => onRead(s)} aria-label={`Mark ${patient} unread`}>Unread</Button>
        )}
      </div>

      <section aria-labelledby="pane-series" className="flex flex-col gap-2">
        <h3 id="pane-series" className="eyebrow m-0">
          Series{detail.data && <> ({detail.data.series.length})</>}
        </h3>
        {detail.isPending ? (
          <Loading rows={2} />
        ) : detail.isError ? (
          <p className="m-0 text-[13px] text-ink-2">The series could not be listed.</p>
        ) : (
          <ul aria-label="Series" className="m-0 flex list-none flex-col gap-1.5 p-0">
            {detail.data.series.map((x: Series) => (
              <li key={x.seriesUid} className="flex items-center gap-2.5 text-[13px]">
                <Thumb src={seriesThumbnailUrl(s.studyUid, x.seriesUid)} />
                <span className="w-5 shrink-0 text-right text-ink-3 tabular-nums">{x.number ?? '·'}</span>
                <span className={chip(x.modality)}>{x.modality}</span>
                <span className="min-w-0 flex-1 truncate">{x.description || 'No description'}</span>
                <span className="shrink-0 text-ink-3 tabular-nums">{x.instances}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="pane-priors" className="flex flex-col gap-2">
        <h3 id="pane-priors" className="eyebrow m-0">
          Earlier studies{detail.data && <> ({detail.data.priors.length})</>}
        </h3>
        {detail.isPending ? (
          <Loading rows={1} />
        ) : detail.isError ? (
          <p className="m-0 text-[13px] text-ink-2">Earlier studies could not be listed.</p>
        ) : detail.data.priors.length === 0 ? (
          <p className="m-0 text-[13px] text-ink-2">No earlier study of this patient.</p>
        ) : (
          <ul aria-label="Earlier studies" className="m-0 flex list-none flex-col gap-2 p-0">
            {detail.data.priors.map((p) => {
              const pm = studyMoment(p.studyDate, p.studyTime);
              return (
                <li key={p.studyUid} className="flex items-center gap-2.5 text-[13px]">
                  <Thumb src={thumbnailUrl(p.studyUid)} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="font-semibold tabular-nums">{when(pm, false)}</span>
                      {p.modalities.map((m) => <span key={m} className={chip(m)}>{m}</span>)}
                    </div>
                    <div className="truncate text-ink-2">{p.description || 'No description'}</div>
                  </div>
                  <Link
                    href={compareUrl(s, p)}
                    target={VIEWER_WINDOW}
                    onPress={() => markOpened(s.studyUid)}
                    aria-label={`Compare with the study of ${when(pm, false)}`}
                    className="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-[13px] font-semibold text-accent-ink no-underline outline-none hover:bg-accent-soft data-[focus-visible]:outline-2 data-[focus-visible]:outline-[var(--focus)]"
                  >
                    Compare <Columns2 aria-hidden size={13} />
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </section>
      </div>
    </aside>
  );
}

function Loading({ rows }: { rows: number }) {
  return (
    <div aria-hidden className="flex flex-col gap-2">
      {Array.from({ length: rows }, (_, i) => <div key={i} className="skel h-[44px] rounded-md" />)}
    </div>
  );
}
