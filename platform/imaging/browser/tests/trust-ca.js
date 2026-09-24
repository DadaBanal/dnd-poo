// Before any test: put the test CA in Chromium's own certificate store (NSS,
// in $HOME/.pki/nssdb), so the browser verifies the front door's certificate
// the way a ward PC verifies PMC's, and keeps what the front door says it may
// keep. Chromium caches nothing from an origin whose certificate it rejects
// (MEASURED, 24 Sep: with certificate errors merely ignored, every open of a
// study fetched the viewer again), so the old ignoreHTTPSErrors would have hidden
// the viewer's caching from the tests.
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

export default function trustCa() {
  const ca = process.env.TEST_CA_SECRET;
  if (!ca || !fs.existsSync(ca)) throw new Error('TEST_CA_SECRET is not set, or the file is missing');
  const db = path.join(os.homedir(), '.pki', 'nssdb');
  fs.mkdirSync(db, { recursive: true });
  const dir = `sql:${db}`;
  if (!fs.existsSync(path.join(db, 'cert9.db'))) execFileSync('certutil', ['-d', dir, '-N', '--empty-password']);
  const listed = execFileSync('certutil', ['-d', dir, '-L']).toString();
  if (!listed.includes('pmc-test-ca')) execFileSync('certutil', ['-d', dir, '-A', '-t', 'C,,', '-n', 'pmc-test-ca', '-i', ca]);
}
