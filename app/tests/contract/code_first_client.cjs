// Real generated requests, Axios interceptors and logger; framework APIs/network are substituted and logs captured.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const ts = require(path.join(root, 'web/node_modules/typescript'));
const axios = require(path.join(root, 'web/node_modules/axios/dist/node/axios.cjs'));
const captures = [];
const notices = [];
const logs = [];
let rejectNext = false;

const transport = {
  ...axios,
  create(config) {
    return axios.create({
      ...config,
      adapter: async (request) => {
        captures.push({
          url: axios.getUri(request), method: request.method, headers: request.headers,
          timeout: request.timeout, data: request.data ? JSON.parse(request.data) : undefined,
        });
        const response = { data: { id: 'one', items: [] }, status: 200, statusText: 'OK', headers: {}, config: request };
        if (rejectNext) {
          rejectNext = false;
          response.status = 403;
          response.data = { detail: { message: 'denied' } };
          throw new axios.AxiosError('denied', 'ERR_BAD_REQUEST', request, {}, response);
        }
        return response;
      },
    });
  },
};

const cache = new Map();
function load(relative) {
  if (cache.has(relative)) return cache.get(relative).exports;
  const module = { exports: {} };
  cache.set(relative, module);
  const output = ts.transpileModule(fs.readFileSync(path.join(root, relative), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
  }).outputText;
  const requireLocal = (name) => {
    if (name === 'axios') return transport;
    if (name === './logging') return load('web/src/lib/api/logging.ts');
    if (name === '../logger') return load('web/src/lib/logger.ts');
    if (name === '@/api/generated/bots/bots') return load('web/src/api/generated/bots/bots.ts');
    if (name === '@/api') return new Proxy({}, { get: () => class LegacyApi {} });
    if (name === 'sonner') return { toast: { error: text => notices.push(text) } };
    if (name === '@/services/cookies') return { getLocale: async () => 'zh-CN' };
    if (name === 'next/headers') return { cookies: async () => ({ getAll: () => [{ name: 'sessionid', value: 'test-session' }] }) };
    throw new Error(`Unexpected dependency ${name}`);
  };
  vm.runInNewContext(output, {
    require: requireLocal, module, exports: module.exports,
    process: { env: { NODE_ENV: 'development', NEXT_PUBLIC_BASE_PATH: '/sapilot', API_SERVER_ENDPOINT: 'http://backend.test', API_SERVER_BASE_PATH: '/api/v1' } },
    performance, URL, Error,
    console: Object.fromEntries(['debug', 'info', 'warn', 'error'].map(level => [level, text => logs.push(JSON.parse(text))])),
  }, { filename: relative });
  return module.exports;
}

(async () => {
  const browser = load('web/src/lib/api/client.ts').apiClient.bots;
  await browser.listBots();
  const update = { is_default: false, description: null, config: { orchestration: { skills: [{ id: 'one', name: 'One', runtime: { top_p: 0.63 }, tools: [] }] } } };
  await browser.updateBot('one', update);
  await browser.deleteBot('one');
  const server = await load('web/src/lib/api/server.ts').getServerApi();
  await server.bots.getBot('one');
  rejectNext = true;
  await assert.rejects(browser.listBots(), error => error.response.status === 403);
  assert.equal(captures[0].url, '/sapilot/api/v1/bots');
  assert.equal(captures[0].timeout, 5000);
  assert.deepEqual(captures[1].data, update);
  assert.equal(captures[2].method, 'delete');
  assert.equal(captures[3].url, 'http://backend.test/api/v1/bots/one');
  assert.equal(captures[3].timeout, 15000);
  assert.equal(captures[3].headers.Lang, 'zh-CN');
  assert.equal(captures[3].headers.Cookie, 'sessionid=test-session');
  assert.deepEqual(notices, ['denied']);
  assert.deepEqual(logs.map(log => log.event), [
    'http.request.completed', 'http.request.completed', 'http.request.completed',
    'http.request.completed', 'http.request.failed',
  ]);
  assert.deepEqual(logs.map(log => log.level), ['DEBUG', 'INFO', 'INFO', 'DEBUG', 'WARNING']);
  assert.equal(logs[4].status_code, 403);
  process.stdout.write(JSON.stringify({ requests: captures.length, browserAndServer: true, preservedPayloadAndErrors: true }));
})().catch(error => { console.error(error); process.exitCode = 1; });
