// The PMC front door app on the platform: at /pmc/, behind the front door's
// sign-in (app.tsx holds the app itself; demo.tsx mounts it as the sample).
import { createRoot } from 'react-dom/client';
import { App, createAppRouter } from './app.tsx';

createRoot(document.getElementById('root')!).render(<App router={createAppRouter({ basepath: '/pmc' })} />);
