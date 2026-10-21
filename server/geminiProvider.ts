import { GoogleGenAI } from '@google/genai';

export type GeminiProviderName = 'direct' | 'proxy' | 'none';

export interface ResolvedGeminiProvider {
  provider: GeminiProviderName;
  client: GoogleGenAI | null;
  /** Human-readable summary for the startup log — never contains a key. */
  detail: string;
}

const VALID_PROVIDERS = new Set(['direct', 'proxy', 'auto']);
const USER_AGENT = 'aistudio-build';

/**
 * Resolves which Gemini provider the commentary server uses.
 *
 * - GEMINI_PROVIDER=direct  → GEMINI_API_KEY is required.
 * - GEMINI_PROVIDER=proxy   → CLIPROXY_BASE_URL + CLIPROXY_API_KEY are required
 *                             (the CLIproxy gateway, native Gemini dialect).
 * - GEMINI_PROVIDER=auto    → direct if GEMINI_API_KEY is set, else proxy if the
 *                             CLIPROXY vars are set, else no client.
 *
 * An invalid GEMINI_PROVIDER value is refused by naming the valid ones — never
 * silently ignored. Key values are never returned or logged; the proxy base URL
 * is not a secret and is included in the detail.
 */
export function resolveGeminiProvider(env: Record<string, string | undefined>): ResolvedGeminiProvider {
  const requested = (env.GEMINI_PROVIDER ?? 'auto').trim().toLowerCase();
  if (!VALID_PROVIDERS.has(requested)) {
    throw new Error(
      `invalid GEMINI_PROVIDER "${env.GEMINI_PROVIDER}"; valid values: direct, proxy, auto`,
    );
  }

  const directKey = env.GEMINI_API_KEY?.trim() || '';
  const proxyBase = env.CLIPROXY_BASE_URL?.trim() || '';
  const proxyKey = env.CLIPROXY_API_KEY?.trim() || '';

  const buildClient = (apiKey: string, baseUrl?: string): GoogleGenAI => {
    const httpOptions: { headers: Record<string, string>; baseUrl?: string } = {
      headers: { 'User-Agent': USER_AGENT },
    };
    if (baseUrl) {
      httpOptions.baseUrl = baseUrl;
    }
    return new GoogleGenAI({ apiKey, httpOptions });
  };

  const directKeySet = directKey.length > 0;
  const proxyConfigured = proxyBase.length > 0 && proxyKey.length > 0;

  const wantDirect = requested === 'direct' || (requested === 'auto' && directKeySet);
  const wantProxy = requested === 'proxy' || (requested === 'auto' && !wantDirect && proxyConfigured);

  if (wantDirect) {
    if (directKey.length === 0) {
      throw new Error('GEMINI_PROVIDER=direct requires GEMINI_API_KEY to be set');
    }
    return { provider: 'direct', client: buildClient(directKey), detail: 'direct (GEMINI_API_KEY)' };
  }

  if (wantProxy) {
    if (!proxyBase || !proxyKey) {
      throw new Error('GEMINI_PROVIDER=proxy requires CLIPROXY_BASE_URL and CLIPROXY_API_KEY to be set');
    }
    return {
      provider: 'proxy',
      client: buildClient(proxyKey, proxyBase),
      detail: `proxy (CLIproxy @ ${proxyBase})`,
    };
  }

  return {
    provider: 'none',
    client: null,
    detail:
      'none configured — set GEMINI_API_KEY, or source .env.private/clients.env.sh and set GEMINI_PROVIDER=proxy',
  };
}
