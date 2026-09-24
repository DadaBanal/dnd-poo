// Tests only: make the off-site container in the Azure stand-in (Azurite),
// as ICT makes the real one once, with its immutability policy, before the
// first copy. The off-site copy never creates a container itself, so a
// missing one fails loudly on site. Runs inside the azurite container:
//   node /pmc/azure-standin-container.mjs
// A container that already exists (409) is fine.
import { createHmac } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { request } from 'node:https';

const account = process.env.PMC_BACKUP_AZURE_ACCOUNT;
const container = process.env.PMC_BACKUP_AZURE_KOPIA_CONTAINER || 'kopia';
const key = Buffer.from(readFileSync('/run/secrets/backup-azure-key', 'utf8').trim(), 'base64');

// Azure's Shared Key signature for "create container": the verb, eleven empty
// standard headers, the x-ms- headers, then the resource.
const date = new Date().toUTCString();
const version = '2025-01-05';
const toSign = 'PUT\n' + '\n'.repeat(11)
  + `x-ms-date:${date}\nx-ms-version:${version}\n`
  + `/${account}/${container}\nrestype:container`;
const signature = createHmac('sha256', key).update(toSign, 'utf8').digest('base64');

const req = request({
  host: `${account}.azurite`, port: 10000, method: 'PUT',
  path: `/${container}?restype=container`,
  ca: readFileSync('/run/secrets/test-ca'),
  headers: {
    'x-ms-date': date, 'x-ms-version': version, 'Content-Length': 0,
    Authorization: `SharedKey ${account}:${signature}`,
  },
}, (res) => {
  let body = '';
  res.on('data', (chunk) => { body += chunk; });
  res.on('end', () => {
    if (res.statusCode === 201) console.log(`off-site container ${container}: created`);
    else if (res.statusCode === 409) console.log(`off-site container ${container}: exists`);
    else { console.error(`off-site container ${container}: HTTP ${res.statusCode}\n${body}`); process.exit(1); }
  });
});
req.on('error', (e) => { console.error(e.message); process.exit(1); });
req.end();
