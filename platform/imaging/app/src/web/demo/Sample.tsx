// The clickable sample's own two pieces: the page that asks who you are
// (in place of the sign-in), and the small pill that says this is a sample.
import { ROLES, type Role } from '../../shared/api.ts';
import { PEOPLE } from './data.ts';
import { chooseRole } from './mock.ts';

const WHO: Record<Role, { title: string; what: string }> = {
  'pmc-radiologist': { title: 'Radiologist', what: 'Sees every study. Claims, reads and marks read.' },
  'pmc-cardiologist': { title: 'Cardiologist', what: 'The same, for the cath lab and echo.' },
  'pmc-technologist': { title: 'Imaging technologist', what: 'Sees every study and opens it; does not claim or read.' },
  'pmc-referrer': { title: 'Referring doctor', what: 'Sees only the studies shared with referrers.' },
  'pmc-ict-admin': { title: 'ICT', what: 'Sees every study; keeps the platform.' },
};

export function Chooser() {
  return (
    <div className="flex min-h-full flex-col" style={{ background: 'var(--bg)', color: 'var(--ink)' }}>
      <div className="seg-bar" aria-hidden="true" />
      <header className="brandbar flex items-center gap-3 px-5 py-2.5">
        <img src="brand/pmc-lockup-white.png" alt="Premiere Medical Center Nueva Ecija" width={1200} height={268} className="h-[34px] w-auto" />
        <span aria-hidden className="divider" />
        <b className="font-display text-[19px] font-extrabold tracking-tight">PMC <span className="quiet">Imaging</span></b>
      </header>
      <main className="mx-auto flex w-full max-w-[720px] flex-1 flex-col gap-5 px-5 py-10">
        <div className="enter">
          <div className="eyebrow">A sample, on invented studies</div>
          <h1 className="m-0 text-[28px] font-extrabold leading-tight tracking-tight">Who are you today?</h1>
          <p className="m-0 mt-2 max-w-[60ch] text-[15px] text-ink-2">
            This is the PMC Imaging front door, as built, running on studies that were invented for it: no patient,
            no engine, no sign-in. Pick a role and the page shows what that person sees. In the platform the role
            comes from your PMC Windows logon.
          </p>
        </div>
        <ul className="enter enter-1 m-0 grid list-none gap-2.5 p-0">
          {ROLES.map((role) => (
            <li key={role}>
              <button
                type="button"
                onClick={() => {
                  chooseRole(role);
                  location.reload();
                }}
                className="flex w-full items-center gap-4 rounded-xl border border-line bg-surface px-4 py-3 text-left shadow-[var(--shadow-2)] outline-none transition-[transform,box-shadow] duration-[var(--t-normal)] hover:-translate-y-px hover:shadow-[var(--shadow)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--focus)]"
              >
                <span className="avatar grid h-9 w-9 shrink-0 place-items-center rounded-full font-display text-[13px] font-extrabold" style={{ background: 'var(--accent-soft)', color: 'var(--accent-ink)' }}>
                  {PEOPLE[role].name.split(' ').map((w) => w[0]).join('').slice(0, 2)}
                </span>
                <span className="min-w-0">
                  <span className="block font-display text-[15px] font-bold">{WHO[role].title}</span>
                  <span className="block text-[13px] text-ink-2">{WHO[role].what}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
        <p className="enter enter-2 m-0 text-[13px] text-ink-3">
          Everything else is the real page: the list, the filters, the keyboard, the preview, claims and read
          marks (they last until you leave), light and dark, and the reading room. The viewer is a picture of the
          real one, because it needs the imaging engine; the pictures are its own renders of the synthetic studies.
        </p>
      </main>
    </div>
  );
}

export function SampleBar({ role }: { role: Role }) {
  return (
    <div
      role="note"
      aria-label="This is a sample"
      className="fixed bottom-3 left-3 z-50 flex items-center gap-2 rounded-full border border-line-2 bg-surface px-3 py-1.5 text-[12.5px] text-ink-2 shadow-[var(--shadow-2)]"
    >
      <span className="live-dot inline-block h-2 w-2 rounded-full" style={{ background: 'var(--orange)' }} aria-hidden />
      <span><b className="text-ink">Sample</b> · invented studies · {WHO[role].title}</span>
      <button
        type="button"
        onClick={() => {
          chooseRole(undefined);
          location.href = location.pathname;
        }}
        className="rounded-full px-2 py-0.5 font-semibold text-accent-ink outline-none hover:bg-accent-soft focus-visible:outline-2 focus-visible:outline-[var(--focus)]"
      >
        Change
      </button>
    </div>
  );
}
