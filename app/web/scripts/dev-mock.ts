import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
import type { MockScenario } from '../src/mocks/handlers';
import { createMockServer } from '../src/mocks/server';

async function main() {
  if (process.env.NODE_ENV === 'production')
    throw new Error('Mock startup is only for local development');
  const args = process.argv.slice(2);
  const index = args.indexOf('--scenario');
  const scenario = index === -1 ? 'default' : args.splice(index, 2)[1];
  if (!['default', 'empty', 'error'].includes(scenario)) {
    throw new Error('--scenario must be default, empty or error');
  }
  const server = createMockServer(scenario as MockScenario);
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const address = server.address();
  if (!address || typeof address === 'string')
    throw new Error('Mock server did not bind');
  const endpoint = `http://127.0.0.1:${address.port}`;
  console.log(
    `[Mock] ${scenario}: ${endpoint}/api/v1 (shared browser/server data)`,
  );
  const require = createRequire(resolve('package.json'));
  const child = spawn(
    process.execPath,
    [
      require.resolve('next/dist/bin/next'),
      'dev',
      '--turbopack',
      '--hostname',
      '127.0.0.1',
      ...args,
    ],
    {
      stdio: 'inherit',
      windowsHide: true,
      env: {
        ...process.env,
        API_SERVER_ENDPOINT: endpoint,
        API_SERVER_BASE_PATH: '/api/v1',
      },
    },
  );
  function stop() {
    if (process.platform === 'win32' && child.pid) {
      spawn('taskkill', ['/pid', String(child.pid), '/t', '/f'], {
        stdio: 'ignore',
        windowsHide: true,
      });
    } else {
      child.kill('SIGTERM');
    }
    server.close();
  }
  process.once('SIGINT', stop);
  process.once('SIGTERM', stop);
  child.once('error', (error) => {
    console.error(error);
    server.close();
    process.exitCode = 1;
  });
  child.once('exit', (code) => {
    server.close();
    process.exitCode = code ?? 0;
  });
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
