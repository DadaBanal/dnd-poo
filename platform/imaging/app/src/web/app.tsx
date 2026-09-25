// The PMC front door app: the page every person lands on at imaging.pmcne.ph.
// main.tsx mounts it on the platform; demo.tsx mounts it as the clickable
// sample, on invented studies and a stand-in for the front door.
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import {
  Outlet, RouterProvider, createRootRoute, createRoute, createRouter, type RouterHistory,
} from '@tanstack/react-router';
import { LogOut, SunMoon } from 'lucide-react';
import { StrictMode, useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { Button } from 'react-aria-components';
import { RoomSearch, WorklistSearch } from '../shared/api.ts';
import { fetchMe, useLiveStudies } from './api.ts';
import { site } from './links.ts';
import { ReadingRoom } from './ReadingRoom.tsx';
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
// here; the choice stays in this browser only, and is applied before the
// first paint, so a page never flashes the other theme.
function applyTheme(theme: string | undefined): void {
  if (theme) document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;
}

const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

function useTheme(): [string | undefined, (from?: HTMLElement | null) => void] {
  const [theme, setTheme] = useState<string | undefined>(() => {
    let chosen: string | undefined;
    try {
      chosen = localStorage.getItem('pmc-theme') ?? undefined;
    } catch {
      chosen = undefined;
    }
    applyTheme(chosen);
    return chosen;
  });
  useEffect(() => applyTheme(theme), [theme]);
  // The new theme spreads from the button in a circle (a view transition,
  // Chromium 111+; elsewhere, or with reduced motion, it simply switches).
  const toggle = (from?: HTMLElement | null) => {
    const dark = theme ? theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    const next = dark ? 'light' : 'dark';
    const apply = () => {
      applyTheme(next);
      setTheme(next);
    };
    try {
      localStorage.setItem('pmc-theme', next);
    } catch {
      // a browser that keeps nothing still gets the theme for this visit
    }
    if (!document.startViewTransition || reducedMotion()) {
      apply();
      return;
    }
    const box = from?.getBoundingClientRect();
    const x = box ? box.left + box.width / 2 : innerWidth;
    const y = box ? box.top + box.height / 2 : 0;
    const reach = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    const transition = document.startViewTransition(() => flushSync(apply));
    transition.ready.then(() => {
      document.documentElement.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${reach}px at ${x}px ${y}px)`] },
        { duration: 420, easing: 'cubic-bezier(0.2, 0, 0, 1)', pseudoElement: '::view-transition-new(root)' },
      );
    }).catch(() => {});
  };
  return [theme, toggle];
}

function Shell() {
  const me = useQuery({ queryKey: ['me'], queryFn: ({ signal }) => fetchMe(signal), staleTime: 60_000 });
  const live = useLiveStudies();
  const [, toggleTheme] = useTheme();
  const themeButton = useRef<HTMLButtonElement>(null);
  const role = me.data?.roles[0];

  return (
    <div className="flex h-full flex-col">
      <div className="seg-bar" aria-hidden="true" />
      {/* The PMC header, as the portal proposal has it: the white lock-up on PMC
          Blue, the loop alone on a phone (brand/, served at /brand/). */}
      <header className="brandbar flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2.5 md:px-5">
        <a href={site.home()} className="flex items-center gap-3 whitespace-nowrap no-underline" style={{ color: 'inherit' }}>
          <img
            src={site.brand('pmc-lockup-white.png')}
            alt="Premiere Medical Center Nueva Ecija"
            width={1200}
            height={268}
            className="hidden h-[34px] w-auto sm:block"
          />
          <img src={site.brand('pmc-mark-white.png')} alt="" width={400} height={288} className="h-[30px] w-auto sm:hidden" />
          <span aria-hidden className="divider hidden sm:block" />
          <b className="font-display text-[19px] font-extrabold tracking-tight">
            PMC <span className="quiet">Imaging</span>
          </b>
        </a>
        <div className="ml-auto flex items-center gap-3.5">
          <span
            className="quiet inline-flex items-center gap-1.5 text-[12.5px]"
            title={live ? 'New studies appear here as they arrive' : 'Reconnecting; the list refreshes every minute meanwhile'}
          >
            <span
              aria-hidden
              className={`inline-block h-2 w-2 rounded-full ${live ? 'live-dot' : ''}`}
              style={{ background: live ? 'var(--brand-live)' : 'rgba(255, 255, 255, .4)' }}
            />
            <span data-testid="live">{live ? 'Live' : 'Connecting'}</span>
          </span>
          {me.data && (
            <span className="flex items-center gap-2 whitespace-nowrap text-[13px]">
              <span
                aria-hidden
                className="avatar grid h-[30px] w-[30px] place-items-center rounded-full font-display text-[12px] font-extrabold"
              >
                {initials(me.data.name)}
              </span>
              <span className="hidden md:inline">
                {me.data.name}
                {role && <span className="quiet"> · {ROLE_NAMES[role]}</span>}
              </span>
            </span>
          )}
          <Button
            ref={themeButton}
            aria-label="Switch between light and dark"
            onPress={() => toggleTheme(themeButton.current)}
            className="hover rounded-lg p-1.5 outline-none data-[focus-visible]:outline-2 data-[focus-visible]:outline-[var(--brand-focus)]"
            style={{ color: 'inherit' }}
          >
            <SunMoon aria-hidden size={17} />
          </Button>
          <a
            href={site.signOut()}
            className="hover inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-[13px] font-semibold no-underline"
            style={{ color: 'inherit' }}
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
// The reading room: the list and the viewer together (ReadingRoom.tsx).
const roomRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/read',
  validateSearch: RoomSearch,
  component: ReadingRoom,
});

// Filters stay plain text in the URL ("?mod=ct,xa&range=today"), so a view
// can be read, typed and shared. Read as text only: the router's own parser
// turns "?q=12345" into a number, and a numeric patient ID would be lost.
export function createAppRouter(options: { basepath?: string; history?: RouterHistory } = {}) {
  return createRouter({
    routeTree: rootRoute.addChildren([worklistRoute, roomRoute]),
    ...(options.basepath ? { basepath: options.basepath } : {}),
    ...(options.history ? { history: options.history } : {}),
    parseSearch: (search) => Object.fromEntries(new URLSearchParams(search)),
    stringifySearch: (search) => {
      const params = new URLSearchParams();
      for (const [k, v] of Object.entries(search)) if (v !== undefined && v !== '') params.set(k, String(v));
      const text = params.toString();
      return text ? `?${text}` : '';
    },
  });
}
export type AppRouter = ReturnType<typeof createAppRouter>;

declare module '@tanstack/react-router' {
  interface Register {
    router: AppRouter;
  }
}

const queries = new QueryClient({
  defaultOptions: { queries: { retry: (n, e) => n < 2 && e.message !== 'signed out', refetchOnWindowFocus: true } },
});

export function App({ router }: { router: AppRouter }) {
  return (
    <StrictMode>
      <QueryClientProvider client={queries}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </StrictMode>
  );
}
