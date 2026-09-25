// The clickable sample: the front door app as built (app.tsx), on invented
// studies answered in the page (demo/mock.ts), with a page that asks who you
// are in place of the sign-in (demo/Sample.tsx). Built by `npm run
// build:demo` into dist-demo/, a folder of files that runs anywhere a
// browser can open it; nothing in it reaches a server.
import { createHashHistory } from '@tanstack/react-router';
import { createRoot } from 'react-dom/client';
import { App, createAppRouter } from './app.tsx';
import { Chooser, SampleBar } from './demo/Sample.tsx';
import { chooseRole, chosenRole, installSample } from './demo/mock.ts';

if (new URLSearchParams(location.search).has('signout')) {
  chooseRole(undefined);
  history.replaceState(null, '', location.pathname + location.hash);
}
const role = chosenRole();
if (role) installSample(role);

createRoot(document.getElementById('root')!).render(
  role ? (
    <>
      <App router={createAppRouter({ history: createHashHistory() })} />
      <SampleBar role={role} />
    </>
  ) : (
    <Chooser />
  ),
);
