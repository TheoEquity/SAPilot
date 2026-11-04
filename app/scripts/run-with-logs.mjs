// Capture a local service's output without adding filesystem code to the browser bundle.
import { spawn } from 'node:child_process';
import { appendFileSync, existsSync, mkdirSync, readFileSync, renameSync, rmSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const settings = JSON.parse(readFileSync(path.join(root, 'config/logging/settings.json'), 'utf8'));
const [service, separator, command, ...args] = process.argv.slice(2);
if (!/^[a-z][a-z-]{0,32}$/.test(service || '') || separator !== '--' || !command) {
  throw new Error('Usage: node scripts/run-with-logs.mjs <service> -- <command> [args]');
}
const directory = path.resolve(root, process.env.SAPILOT_LOG_DIR || settings.directory);
mkdirSync(directory, { recursive: true });
const filename = path.join(directory, service + '.log');
let warned = false;
function write(chunk, stream) {
  stream.write(chunk);
  try {
    if (existsSync(filename) && statSync(filename).size + chunk.length > settings.max_bytes) {
      rmSync(filename + '.' + settings.backup_count, { force: true });
      for (let n = settings.backup_count - 1; n >= 1; n--) {
        if (existsSync(filename + '.' + n)) renameSync(filename + '.' + n, filename + '.' + (n + 1));
      }
      renameSync(filename, filename + '.1');
    }
    appendFileSync(filename, chunk);
  } catch {
    if (!warned) process.stderr.write('Service log file unavailable; console output continues.\n');
    warned = true;
  }
}
const child = spawn(command, args, { stdio: ['inherit', 'pipe', 'pipe'], windowsHide: true });
child.stdout.on('data', (chunk) => write(chunk, process.stdout));
child.stderr.on('data', (chunk) => write(chunk, process.stderr));
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
child.on('error', () => { process.exitCode = 1; });
child.on('exit', (code) => { process.exitCode = code ?? 1; });
