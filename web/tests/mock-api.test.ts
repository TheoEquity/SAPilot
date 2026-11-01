import axios from 'axios';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { createServer } from 'node:http';
import test from 'node:test';
import { getBots } from '../src/api/generated/bots/bots';
import type { MockScenario } from '../src/mocks/handlers';
import { createMockServer } from '../src/mocks/server';

async function start(scenario: MockScenario = 'default') {
  const server = createMockServer(scenario);
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const address = server.address();
  assert(address && typeof address !== 'string');
  return { server, url: `http://127.0.0.1:${address.port}/api/v1` };
}

test('generated client CRUD and browser proxy share data with server reads', async (t) => {
  const { server, url } = await start();
  t.after(() => server.close());
  // Same proxy path as the app: browser requests go through the frontend host.
  const proxy = createServer(async (req, res) => {
    const chunks: Buffer[] = [];
    for await (const chunk of req) chunks.push(Buffer.from(chunk));
    const body = Buffer.concat(chunks);
    const result = await fetch(new URL(req.url!, url), {
      method: req.method,
      ...(body.length ? { body: new Uint8Array(body).buffer } : {}),
      headers: { 'Content-Type': 'application/json' },
    });
    res.writeHead(result.status, Object.fromEntries(result.headers));
    res.end(Buffer.from(await result.arrayBuffer()));
  });
  proxy.listen(0, '127.0.0.1');
  await once(proxy, 'listening');
  t.after(() => proxy.close());
  const address = proxy.address();
  assert(address && typeof address !== 'string');
  const browser = getBots(
    axios.create({
      baseURL: `http://127.0.0.1:${address.port}/api/v1`,
      proxy: false,
    }),
  );
  const ssr = getBots(axios.create({ baseURL: url, proxy: false }));
  assert.equal((await ssr.listBots()).data.items?.[0].title, 'Mock SAP Bot');
  const created = await browser.createBot({
    title: 'Created in browser',
    type: 'agent',
  });
  assert(created.data.id);
  const id = created.data.id;
  assert.equal((await ssr.getBot(id)).data.title, 'Created in browser');
  assert((await ssr.listBots()).data.items?.some((item) => item.id === id));
  await browser.updateBot(id, { description: null, title: 'Edited' });
  assert.equal((await ssr.getBot(id)).data.title, 'Edited');
  await browser.deleteBot(id);
  await assert.rejects(
    ssr.getBot(id),
    (err: unknown) => axios.isAxiosError(err) && err.response?.status === 404,
  );
  await assert.rejects(
    ssr.deleteBot('mock-bot'),
    (err: unknown) => axios.isAxiosError(err) && err.response?.status === 400,
  );
  assert.equal(
    (await fetch(url + '/user').then((r) => r.json())).username,
    'mock-developer',
  );
  assert.equal((await fetch(url + '/unknown-operation')).status, 501);
  // A different instance cannot see this instance's state.
  const other = await start('empty');
  t.after(() => other.server.close());
  assert.deepEqual(
    (await fetch(other.url + '/bots').then((r) => r.json())).items,
    [],
  );
});

test('empty and error scenarios are repeatable and never call a real backend', async (t) => {
  for (const scenario of ['empty', 'error'] as const) {
    const { server, url } = await start(scenario);
    t.after(() => server.close());
    const api = getBots(axios.create({ baseURL: url, proxy: false }));
    if (scenario === 'empty') {
      assert.deepEqual((await api.listBots()).data.items, []);
      await api.createBot({ title: 'First Bot' });
      assert.equal((await api.listBots()).data.items?.length, 1);
    } else {
      await assert.rejects(
        api.listBots(),
        (err: unknown) =>
          axios.isAxiosError(err) && err.response?.status === 500,
      );
      await assert.rejects(
        api.createBot({ title: 'Fails' }),
        (err: unknown) =>
          axios.isAxiosError(err) && err.response?.status === 500,
      );
    }
  }
});
