import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

test('local frontend output uses the shared override and preserves exit status', (t) => {
  const directory = mkdtempSync(path.join(tmpdir(), 'sapilot-log-'));
  t.after(() => {
    assert.equal(path.dirname(directory), tmpdir());
    rmSync(directory, { recursive: true });
  });
  const script = fileURLToPath(
    new URL('../../scripts/run-with-logs.mjs', import.meta.url),
  );
  const result = spawnSync(
    process.execPath,
    [
      script,
      'frontend',
      '--',
      process.execPath,
      '-e',
      'console.log("frontend.started"); console.error("frontend.failed"); process.exitCode=7;',
    ],
    { env: { ...process.env, SAPILOT_LOG_DIR: directory }, encoding: 'utf8' },
  );
  assert.equal(result.status, 7);
  assert.match(result.stdout, /frontend.started/);
  assert.match(result.stderr, /frontend.failed/);
  const saved = readFileSync(path.join(directory, 'frontend.log'), 'utf8');
  assert.match(saved, /frontend.started/);
  assert.match(saved, /frontend.failed/);
});
