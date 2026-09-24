// Who is asking. The front door signs people in and passes each request's
// access token on (Authorization: Bearer). This server checks that token
// itself, against Keycloak's signing keys, before it believes a word of it:
// anything else on the engine network could otherwise claim to be anyone.
import type { Context } from 'hono';
import { jwk } from 'hono/jwk';
import type { HonoJsonWebKey } from 'hono/utils/jwt/jws';
import { ROLES, type Me, type Role } from '../shared/api.ts';

const REALM = process.env.KEYCLOAK_REALM_URL ?? 'http://keycloak:8080/auth/realms/pmc';
const ISSUER = `https://${process.env.PMC_HOSTNAME ?? 'imaging.pmcne.ph'}/auth/realms/pmc`;
const CLIENT = 'pmc-front-door';

// Keycloak's public keys, fetched once and again whenever a token names a key
// this server has not seen (Keycloak rotates them).
let keys: HonoJsonWebKey[] = [];
let fetchedAt = 0;

async function signingKeys(c: Context): Promise<HonoJsonWebKey[]> {
  const header = c.req.header('Authorization') ?? '';
  const kid = (() => {
    try {
      return JSON.parse(Buffer.from(header.split(' ')[1]?.split('.')[0] ?? '', 'base64url').toString()).kid;
    } catch {
      return undefined;
    }
  })();
  const known = keys.some((k) => k.kid === kid);
  if (!known && Date.now() - fetchedAt > 10_000) {
    const r = await fetch(`${REALM}/protocol/openid-connect/certs`, { signal: AbortSignal.timeout(10_000) });
    if (r.ok) {
      keys = ((await r.json()) as { keys: HonoJsonWebKey[] }).keys.filter((k) => k.use !== 'enc');
      fetchedAt = Date.now();
    }
  }
  return keys;
}

// Verifies the signature, the expiry and the issuer. The token must also
// have been issued to the front door itself.
export const signedIn = jwk({ keys: signingKeys, alg: ['RS256'], verification: { iss: ISSUER } });

interface Claims {
  azp?: string;
  email?: string;
  name?: string;
  preferred_username?: string;
  realm_access?: { roles?: string[] };
}

export function person(c: Context): Me | undefined {
  const claims = c.get('jwtPayload') as Claims | undefined;
  if (!claims || claims.azp !== CLIENT || !claims.preferred_username) return undefined;
  const roles = (claims.realm_access?.roles ?? []).filter((r): r is Role => (ROLES as readonly string[]).includes(r));
  return {
    username: claims.preferred_username,
    name: claims.name ?? claims.preferred_username,
    email: claims.email ?? '',
    roles,
  };
}

export function bearer(c: Context): string {
  return (c.req.header('Authorization') ?? '').replace(/^Bearer\s+/i, '');
}
