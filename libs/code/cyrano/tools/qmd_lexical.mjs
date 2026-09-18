/** Explicit project-local QMD lexical bridge. No product authority or LLM calls. */
import { readFile, realpath, lstat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { dirname, join, relative, isAbsolute } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const tools = dirname(fileURLToPath(import.meta.url));
const state = join(tools, '.state', 'qmd');
const [manifestPath, query] = process.argv.slice(2);
if (!manifestPath || !query || process.argv.length !== 4) {
  console.error('Usage: node cyrano/tools/qmd_lexical.mjs <corpus-manifest.json> <query>');
  process.exit(2);
}
const sha = data => createHash('sha256').update(data).digest('hex');
let store;
try {
  const receipt = JSON.parse(await readFile(join(state, 'install-receipt.json'), 'utf8'));
  if (sha(await readFile(join(state, 'package-lock.json'))) !== receipt.lock_sha256) {
    throw new Error('QMD_LOCK_CHANGED');
  }
  const corpusRoot = await realpath(join(tools, '.state', 'corpus'));
  const file = await realpath(manifestPath);
  const rel = relative(corpusRoot, file);
  if (rel.startsWith('..') || isAbsolute(rel)) throw new Error('CORPUS_ESCAPE');
  const corpus = JSON.parse(await readFile(file, 'utf8'));
  if (corpus.kind !== 'developer_readset_export') throw new Error('INVALID_CORPUS');
  const root = dirname(file);
  for (const document of corpus.documents) {
    if (!/^\d{4}\.md$/.test(document.exported)) throw new Error('INVALID_EXPORT_PATH');
    const p = join(root, document.exported);
    if ((await lstat(p)).isSymbolicLink()) throw new Error('CORPUS_LINK');
    if (sha(await readFile(p)) !== document.sha256) throw new Error('CORPUS_CHANGED');
  }
  const packageRoot = join(state, 'node_modules', '@tobilu', 'qmd');
  const pkg = JSON.parse(await readFile(join(packageRoot, 'package.json'), 'utf8'));
  if (pkg.version !== '2.8.3') throw new Error('QMD_VERSION_MISMATCH');
  const { createStore } = await import(pathToFileURL(join(packageRoot, 'dist', 'index.js')));
  store = await createStore({
    dbPath: join(state, `corpus-${corpus.readset_digest}.sqlite`),
    config: { collections: { docs: { path: root, pattern: '*.md' } } },
  });
  await store.update({ collections: ['docs'] });
  const results = await store.searchLex(query, { limit: 10 });
  console.log(JSON.stringify({ kind: 'developer_lexical_results', results }, null, 2));
} catch (error) {
  console.error(JSON.stringify({ status: 'blocked', error: String(error) }));
  process.exitCode = 2;
} finally {
  if (store) await store.close();
}
