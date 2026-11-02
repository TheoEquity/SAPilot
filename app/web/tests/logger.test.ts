import axios from 'axios';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createServer } from 'node:http';
import test from 'node:test';
import { attachRequestLogging } from '../src/lib/api/logging';
import { logger } from '../src/lib/logger';

test('logger keeps safe fields, omits payloads and never throws on output failure', (t) => {
  const events: Record<string, unknown>[] = [];
  t.mock.method(console, 'error', (record: string) =>
    events.push(JSON.parse(record)),
  );
  logger.error('upload.failed', {
    document_id: 'doc-test',
    error: Object.assign(new Error('PRIVATE text token=secret'), {
      config: { headers: { Authorization: 'PRIVATE' } },
    }),
    body: 'PRIVATE document',
  } as Parameters<typeof logger.error>[1]);
  assert.equal(events[0].document_id, 'doc-test');
  assert.equal(events[0].error_type, 'Error');
  assert.equal(events[0].service, 'frontend-server');
  assert.equal(JSON.stringify(events).includes('PRIVATE'), false);
  t.mock.method(console, 'error', () => {
    throw new Error('output unavailable');
  });
  assert.doesNotThrow(() => logger.error('upload.failed'));
});

test('request logging preserves responses and failures, strips query and records existing trace', async (t) => {
  const events: Record<string, unknown>[] = [];
  for (const level of ['info', 'warn', 'error', 'debug'] as const) {
    t.mock.method(console, level, (record: string) =>
      events.push(JSON.parse(record)),
    );
  }
  const server = createServer((req, res) => {
    res.setHeader('X-Trace-ID', '0123456789abcdef0123456789abcdef');
    res.statusCode = req.url?.startsWith('/fail') ? 503 : 200;
    res.end('{}');
  }).listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => server.close());
  const address = server.address();
  assert(address && typeof address !== 'string');
  const client = axios.create({ baseURL: `http://127.0.0.1:${address.port}` });
  attachRequestLogging(client);
  assert.equal(
    (await client.post('/upload?token=PRIVATE', { query: 'PRIVATE' })).status,
    200,
  );
  let caught: unknown;
  try {
    await client.post('/fail?token=PRIVATE');
  } catch (error) {
    caught = error;
  }
  assert(axios.isAxiosError(caught));
  assert.equal(caught.response?.status, 503);
  const success = events.find((e) => e.event === 'http.request.completed');
  assert.equal(success?.path, '/upload');
  assert.equal(success?.trace_id, '0123456789abcdef0123456789abcdef');
  assert.equal(typeof success?.duration_ms, 'number');
  assert(events.some((e) => e.event === 'http.request.failed'));
  assert.equal(JSON.stringify(events).includes('PRIVATE'), false);
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(
    client.post('/cancel', {}, { signal: controller.signal }),
    axios.isCancel,
  );
  assert(
    events.some(
      (e) => e.event === 'http.request.cancelled' && e.level === 'INFO',
    ),
  );
});

test('browser events are identified and production debug stays silent', (t) => {
  const events: Record<string, unknown>[] = [];
  t.mock.method(console, 'info', (record: string) =>
    events.push(JSON.parse(record)),
  );
  t.mock.method(console, 'debug', () =>
    assert.fail('production debug must stay silent'),
  );
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
  const previousEnv = process.env.NODE_ENV;
  Object.defineProperty(globalThis, 'window', {
    value: {},
    configurable: true,
  });
  Reflect.set(process.env, 'NODE_ENV', 'production');
  try {
    logger.info('chat.message.submitted', { chat_id: 'chat-test' });
    logger.debug('http.request.completed');
    assert.equal(events[0].service, 'browser');
  } finally {
    if (previousWindow)
      Object.defineProperty(globalThis, 'window', previousWindow);
    else Reflect.deleteProperty(globalThis, 'window');
    if (previousEnv === undefined)
      Reflect.deleteProperty(process.env, 'NODE_ENV');
    else Reflect.set(process.env, 'NODE_ENV', previousEnv);
  }
});

test('network errors keep the original rejection and omit its message', async (t) => {
  const events: Record<string, unknown>[] = [];
  t.mock.method(console, 'error', (record: string) =>
    events.push(JSON.parse(record)),
  );
  const error = new axios.AxiosError('PRIVATE network detail', 'ERR_NETWORK');
  const client = axios.create({
    adapter: async () => {
      throw error;
    },
  });
  attachRequestLogging(client);
  await assert.rejects(client.post('/upload'), (caught) => caught === error);
  assert.equal(events[0].event, 'http.request.failed');
  assert.equal(events[0].error_code, 'ERR_NETWORK');
  assert.equal(JSON.stringify(events).includes('PRIVATE'), false);
});
