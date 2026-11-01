const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const ts = require('typescript');

// Render the real provider with React; substitute only network and Next APIs.
function provider(api, chats = []) {
  const logs = [];
  const cache = new Map();
  function load(relative) {
    if (cache.has(relative)) return cache.get(relative).exports;
    const module = { exports: {} };
    cache.set(relative, module);
    const source = fs.readFileSync(path.join(__dirname, '..', relative), 'utf8');
    const output = ts.transpileModule(source, {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
        jsx: ts.JsxEmit.ReactJSX,
        esModuleInterop: true,
      },
    }).outputText;
    function requireLocal(name) {
      if (name === 'react' || name === 'react/jsx-runtime') return require(name);
      if (name === '@/lib/api/client') return { apiClient: { defaultApi: api } };
      if (name === '@/lib/logger') return load('src/lib/logger.ts');
      if (name === 'next-intl') return { useLocale: () => 'zh-CN' };
      if (name === 'next/navigation') return {
        useParams: () => ({ botId: 'bot-test' }),
        usePathname: () => '/workspace/bots/bot-test/chats/chat-test',
        useRouter: () => ({ push() {} }),
      };
      throw new Error(`Unexpected dependency ${name}`);
    }
    vm.runInNewContext(output, {
      require: requireLocal, module, exports: module.exports, Error, URL,
      process: { env: { NODE_ENV: 'test' } },
      console: Object.fromEntries(['debug', 'info', 'warn', 'error'].map(level => [
        level, record => logs.push(JSON.parse(record)),
      ])),
    }, { filename: relative });
    return module.exports;
  }
  const { BotProvider, useBotContext } = load('src/components/providers/bot-provider.tsx');
  let context;
  function Probe() {
    context = useBotContext();
    return null;
  }
  renderToStaticMarkup(React.createElement(BotProvider, {
    bot: { id: 'bot-test' }, chats, workspace: true,
  }, React.createElement(Probe)));
  return { context, logs };
}

const chat = { id: 'chat-test', bot_id: 'bot-test', title: 'New Chat' };

test('title generation failure is contained without rejecting the chat callback', async () => {
  let writes = 0;
  const error = Object.assign(new Error('PRIVATE request token'), {
    name: 'AxiosError', response: { status: 400 },
  });
  const { context, logs } = provider({
    botsBotIdChatsChatIdTitlePost: async () => { throw error; },
    botsBotIdChatsChatIdPut: async () => { writes += 1; },
  });
  await assert.doesNotReject(context.chatRename(chat));
  assert.equal(writes, 0);
  assert.equal(chat.title, 'New Chat');
  assert.equal(logs.length, 1);
  assert.equal(logs[0].event, 'chat.title.failed');
  assert.equal(logs[0].level, 'WARNING');
  assert.equal(logs[0].chat_id, chat.id);
  assert.equal(logs[0].error_type, 'AxiosError');
  assert.equal(JSON.stringify(logs).includes('PRIVATE'), false);
});

test('title saving or list refresh failures are contained', async (t) => {
  for (const failAt of ['save', 'reload']) {
    await t.test(failAt, async () => {
      const { context, logs } = provider({
        botsBotIdChatsChatIdTitlePost: async () => ({ data: { title: 'Generated title' } }),
        botsBotIdChatsChatIdPut: async () => {
          if (failAt === 'save') throw new Error('save failed');
        },
        botsBotIdChatsGet: async () => { throw new Error('reload failed'); },
      });
      await assert.doesNotReject(context.chatRename(chat));
      assert.equal(logs.length, 1);
      assert.equal(logs[0].event, 'chat.title.failed');
    });
  }
});

test('successful automatic title saves the title and awaits the list refresh', async () => {
  const calls = [];
  let release;
  const reload = new Promise(resolve => { release = resolve; });
  const { context, logs } = provider({
    botsBotIdChatsChatIdTitlePost: async (payload) => {
      calls.push(['generate', payload]);
      return { data: { title: 'Generated title' } };
    },
    botsBotIdChatsChatIdPut: async (payload) => { calls.push(['save', payload]); },
    botsBotIdChatsGet: async () => { calls.push(['reload']); await reload; return { data: { items: [] } }; },
  });
  let settled = false;
  const pending = context.chatRename(chat).then(() => { settled = true; });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(settled, false);
  assert.deepEqual(calls.map(([name]) => name), ['generate', 'save', 'reload']);
  assert.equal(calls[0][1].titleGenerateRequest.language, 'zh-CN');
  assert.equal(calls[1][1].chatUpdate.title, 'Generated title');
  release();
  await pending;
  assert.deepEqual(logs, []);
});

test('custom or incomplete chats are not renamed', async () => {
  const { context, logs } = provider({
    botsBotIdChatsChatIdTitlePost: async () => { assert.fail('must not generate'); },
  });
  for (const value of [{ ...chat, title: 'Custom' }, { ...chat, id: '' }, { ...chat, bot_id: '' }]) {
    await context.chatRename(value);
  }
  assert.deepEqual(logs, []);
});
