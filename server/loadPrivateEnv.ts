import fs from 'fs';
import path from 'path';

/**
 * Loads the operator's gitignored private env file into process.env, without
 * overriding anything the real environment already set. Bun auto-loads `.env`
 * files from the project root, but NOT this custom path — and the file uses
 * shell `export KEY=value` syntax. Values are never logged or returned.
 *
 * Returns the number of variables loaded from the file.
 */
export function loadPrivateEnv(
  repoRoot: string,
  env: Record<string, string | undefined> = process.env as Record<string, string | undefined>,
): number {
  const file = path.join(repoRoot, '.env.private', 'clients.env.sh');
  if (!fs.existsSync(file)) return 0;

  let loaded = 0;
  for (const raw of fs.readFileSync(file, 'utf8').split('\n')) {
    const line = raw.trim();
    if (line.length === 0 || line.startsWith('#')) continue;
    const withoutExport = line.startsWith('export ') ? line.slice(7).trim() : line;
    const eq = withoutExport.indexOf('=');
    if (eq <= 0) continue;
    const key = withoutExport.slice(0, eq).trim();
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) continue;
    let value = withoutExport.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"') && value.length >= 2) ||
      (value.startsWith("'") && value.endsWith("'") && value.length >= 2)
    ) {
      value = value.slice(1, -1);
    }
    if (env[key] === undefined || env[key] === '') {
      env[key] = value;
      loaded++;
    }
  }
  return loaded;
}
