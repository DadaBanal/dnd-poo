// The PMC front door app: the page every person lands on at imaging.pmcne.ph.
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { Outlet, RouterProvider, createRootRoute, createRoute, createRouter } from '@tanstack/react-router';
import { LogOut, SunMoon } from 'lucide-react';
import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Button } from 'react-aria-components';
import { WorklistSearch } from '../shared/api.ts';
import { fetchMe, useLiveStudies } from './api.ts';
import { Worklist } from './Worklist.tsx';
import './styles.css';

const ROLE_NAMES = {
  'pmc-radiologist': 'Radiology',
  'pmc-cardiologist': 'Cardiology',
  'pmc-technologist': 'Imaging technologist',
  'pmc-referrer': 'Referring doctor',
  'pmc-ict-admin': 'ICT',
} as const;

// The page follows the PC's light or dark setting unless the person picks one
// here; the choice stays in this browser only.
function useTheme(): [string | undefined, () => void] {
  const [theme, setTheme] = useState<string | undefined>(() => {
    try {
      return localStorage.getItem('pmc-theme') ?? undefined;
    } catch {
      return undefined;
    }
  });
  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
  }, [theme]);
  const toggle = () => {
    const dark = theme ? theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    const next = dark ? 'light' : 'dark';
    setTheme(next);
    try {
      localStorage.setItem('pmc-theme', next);
    } catch {
      // a browser that keeps nothing still gets the theme for this visit
    }
  };
  return [theme, toggle];
}

function Shell() {
  const me = useQuery({ queryKey: ['me'], queryFn: ({ signal }) => fetchMe(signal), staleTime: 60_000 });
  const live = useLiveStudies();
  const [, toggleTheme] = useTheme();
  const role = me.data?.roles[0];

  return (
    <div className="flex h-full flex-col">
      <div className="ribbon" aria-hidden="true" />
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line bg-surface px-4 py-2.5 md:px-5">
        <a href="/pmc/" className="flex items-baseline gap-2.5 whitespace-nowrap text-ink no-underline">
          <b className="font-display text-[19px] font-extrabold tracking-tight">
            PMC <span className="text-accent-ink">Imaging</span>
          </b>
          <span className="hidden text-[12.5px] text-ink-3 sm:inline">Premiere Medical Center Nueva Ecija</span>
        </a>
        <div className="ml-auto flex items-center gap-3.5">
          <span
            className="inline-flex items-center gap-1.5 text-[12.5px] text-ink-3"
            title={live ? 'New studies appear here as they arrive' : 'Reconnecting; the list refreshes every minute meanwhile'}
          >
            <span aria-hidden className={`inline-block h-2 w-2 rounded-full ${live ? 'bg-ok' : 'bg-line-2'}`} />
            <span data-testid="live">{live ? 'Live' : 'Connecting'}</span>
          </span>
          {me.data && (
            <span className="flex items-center gap-2 whitespace-nowrap text-[13px] text-ink-2">
              <span
                aria-hidden
                className="grid h-[30px] w-[30px] place-items-center rounded-full bg-blue-soft font-display text-[12px] font-extrabold text-blue-ink"
              >
                {initials(me.data.name)}
              </span>
              <span className="hidden md:inline">
                {me.data.name}
                {role && <span className="text-ink-3"> · {ROLE_NAMES[role]}</span>}
              </span>
            </span>
          )}
          <Button
            aria-label="Switch between light and dark"
            onPress={toggleTheme}
            className="rounded-lg p-1.5 text-ink-2 outline-none hover:bg-surface-2 data-[focus-visible]:outline-2 data-[focus-visible]:outline-[var(--focus)]"
          >
            <SunMoon aria-hidden size={17} />
          </Button>
          <a
            href="/oauth2/sign_out"
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-[13px] font-semibold text-ink-2 no-underline hover:bg-surface-2"
          >
            <LogOut aria-hidden size={15} />
            Sign out
          </a>
        </div>
      </header>
      <main className="flex min-h-0 flex-1 flex-col">
        <Outlet />
      </main>
    </div>
  );
}

function initials(name: string): string {
  const parts = name.replace(/[^\p{L}\s]/gu, ' ').trim().split(/\s+/);
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1]?.[0] ?? '' : '')).toUpperCase() || '?';
}

const rootRoute = createRootRoute({ component: Shell });
const worklistRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  validateSearch: WorklistSearch,
  component: Worklist,
});

// Filters stay plain text in the URL ("?mod=ct,xa&range=today"), so a view
// can be read, typed and shared. Read as text only: the router's own parser
// turns "?q=12345" into a number, and a numeric patient ID would be lost.
const router = createRouter({
  routeTree: rootRoute.addChildren([worklistRoute]),
  basepath: '/pmc',
  parseSearch: (search) => Object.fromEntries(new URLSearchParams(search)),
  stringifySearch: (search) => {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(search)) if (v !== undefined && v !== '') params.set(k, String(v));
    const text = params.toString();
    return text ? `?${text}` : '';
  },
});

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

const queries = new QueryClient({
  defaultOptions: { queries: { retry: (n, e) => n < 2 && e.message !== 'signed out', refetchOnWindowFocus: true } },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queries}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
