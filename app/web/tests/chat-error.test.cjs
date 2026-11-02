const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');

// Real hook and logger; provide hook state and substitute external socket/Next IO.
function chatHook({ locale = 'zh-CN' } = {}) {
  const states = [];
  const logs = [];
  const renames = [];
  let cursor = 0;
  let socketCallbacks;
  const socket = {};
  const connections = { disconnect: 0, connect: 0 };
  const react = {
    useState(initial) {
      const index = cursor++;
      states[index] = initial;
      return [initial, next => { states[index] = typeof next === 'function' ? next(states[index]) : next; }];
    },
    useCallback: fn => fn,
    useMemo: fn => fn(),
    useRef: initial => ({ current: initial }),
    useEffect() {},
  };
  function load(relative) {
    const module = { exports: {} };
    const output = ts.transpileModule(fs.readFileSync(path.join(__dirname, '..', relative), 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText;
    function requireLocal(name) {
      if (name === 'react') return react;
      if (name === '@/lib/logger') return load('src/lib/logger.ts');
      if (name === '@/lib/api/client') return { apiClient: {} };
      if (name === '@/components/providers/bot-provider') return { useBotContext: () => ({ chatRename: chat => renames.push(chat) }) };
      if (name === 'next-intl') return {
        useLocale: () => locale,
        useTranslations: namespace => key => {
          const messages = JSON.parse(fs.readFileSync(path.join(__dirname, '../src/i18n', locale, namespace + '.json'), 'utf8'));
          assert.equal(typeof messages[key], 'string', `Missing ${locale}.${namespace}.${key}`);
          return messages[key];
        },
      };
      if (name === 'next/navigation') return { useParams: () => ({ botId: 'bot-test', chatId: 'chat-test' }) };
      if (name === 'react-scroll') return { animateScroll: { scrollToBottom() {} } };
      if (name === 'ahooks') return {
        useWebSocket: (_url, options) => {
          socketCallbacks = options;
          return {
            sendMessage() {}, readyState: 1,
            disconnect() { connections.disconnect++; options.onClose({ code: 1000 }, socket); },
            connect() { connections.connect++; },
          };
        },
      };
      throw new Error(`Unexpected dependency ${name}`);
    }
    vm.runInNewContext(output, {
      require: requireLocal, module, exports: module.exports, Error, URL,
      process: { env: { NODE_ENV: 'test' } },
      console: Object.fromEntries(['info', 'warn', 'error', 'debug'].map(level => [level, record => logs.push(JSON.parse(record))])),
    }, { filename: relative });
    return module.exports;
  }
  const chat = { id: 'chat-test', bot_id: 'bot-test', history: [] };
  const actions = load('src/components/chat/use-chat-messages.ts').useChatMessages(chat);
  return {
    states, logs, renames, connections,
    receive: (event, ws = socket) => socketCallbacks.onMessage({ data: JSON.stringify(event) }, ws),
    close: (code = 1006, ws = socket) => socketCallbacks.onClose({ code, reason: 'PRIVATE close reason' }, ws),
    connectionError: (ws = socket) => socketCallbacks.onError({}, ws),
    cancel: actions.handleCancel,
  };
}

test('server error ends waiting and keeps its visible message without a console error overlay', () => {
  const h = chatHook();
  h.receive({ id: 'message-test', type: 'start' });
  assert.equal(h.states[1], true);
  h.receive({ id: 'error', type: 'error', data: '请先在 Agent 设置中配置模型。' });
  assert.equal(h.states[1], false);
  assert.equal(h.states[0].at(-1)[0].type, 'error');
  assert.equal(h.states[0].at(-1)[0].data, '请先在 Agent 设置中配置模型。');
  assert.equal(h.logs.at(-1).event, 'chat.response.failed');
  assert.equal(h.logs.at(-1).level, 'WARNING');
  assert.equal(h.logs.at(-1).status, 'failed');
  assert.equal(h.logs.at(-1).chat_id, 'chat-test');
  assert.equal(JSON.stringify(h.logs).includes('请先'), false);
  assert.deepEqual(h.renames, []);
});

test('legacy error ID also ends waiting', () => {
  const h = chatHook();
  h.receive({ id: 'message-test', type: 'start' });
  h.receive({ id: 'error', data: 'request failed' });
  assert.equal(h.states[1], false);
  assert.equal(h.logs.at(-1).level, 'WARNING');
});

test('a later normal response still accumulates text and completes after a server error', () => {
  const h = chatHook();
  h.receive({ id: 'error', type: 'error', data: 'request failed' });
  h.receive({ id: 'next-message', type: 'start' });
  h.receive({ id: 'next-message', type: 'message', data: 'hello' });
  h.receive({ id: 'next-message', type: 'message', data: ' again' });
  h.receive({ id: 'next-message', type: 'stop', data: [] });
  assert.equal(h.states[1], false);
  assert.equal(h.states[0].at(-1).find(part => part.type === 'message').data, 'hello again');
  assert.equal(h.renames.length, 1);
});

test('malformed socket data remains an unexpected error', () => {
  const h = chatHook();
  assert.throws(() => h.receive(undefined));
  assert.equal(h.logs.at(-1).event, 'chat.response.invalid');
  assert.equal(h.logs.at(-1).level, 'ERROR');
});

test('unexpected disconnect ends waiting and preserves the partial answer with one inline error', () => {
  const h = chatHook();
  h.receive({ id: 'message-test', type: 'start' });
  h.receive({ id: 'message-test', type: 'message', data: 'Already received text.' });
  h.close();
  assert.equal(h.states[1], false);
  const parts = h.states[0].at(-1);
  assert.equal(parts.find(part => part.type === 'message').data, 'Already received text.');
  const error = parts.find(part => part.type === 'error');
  assert.equal(error.id, 'message-test');
  assert.equal(error.data, '连接已断开，本次回答未完成。请在连接恢复后重试。');
  assert.equal(JSON.stringify(h.logs).includes('PRIVATE'), false);
  assert.deepEqual(h.renames, []);
});

test('socket error followed by close ends waiting and shows the interruption only once', () => {
  const h = chatHook({ locale: 'en-US' });
  h.receive({ id: 'message-test', type: 'start' });
  h.connectionError();
  assert.equal(h.states[1], false);
  h.close();
  const errors = h.states[0].flat().filter(part => part.type === 'error');
  assert.equal(errors.length, 1);
  assert.equal(errors[0].data, 'Connection lost. This answer is incomplete. Please retry once reconnected.');
});

test('a normal socket close before stop also ends an unfinished response', () => {
  const h = chatHook();
  h.receive({ id: 'message-test', type: 'start' });
  h.close(1000);
  assert.equal(h.states[1], false);
  assert.equal(h.states[0].flat().filter(part => part.type === 'error').length, 1);
});

test('close after stop or a server error does not add a connection failure', () => {
  for (const terminal of [{ id: 'message-test', type: 'stop', data: [] }, { id: 'error', type: 'error', data: 'Server error' }]) {
    const h = chatHook();
    h.receive({ id: 'message-test', type: 'start' });
    h.receive(terminal);
    const before = JSON.stringify(h.states[0]);
    h.close();
    assert.equal(h.states[1], false);
    assert.equal(JSON.stringify(h.states[0]), before);
  }
});

test('user cancellation ends waiting and reconnects without a failure message', () => {
  const h = chatHook();
  h.receive({ id: 'message-test', type: 'start' });
  h.cancel();
  h.close();
  assert.equal(h.states[1], false);
  assert.deepEqual(h.connections, { disconnect: 1, connect: 1 });
  assert.equal(h.states[0].flat().filter(part => part.type === 'error').length, 0);
});

test('a late close from the old socket cannot interrupt the next answer', () => {
  const h = chatHook();
  h.receive({ id: 'old-message', type: 'start' });
  h.close();
  const freshSocket = {};
  h.receive({ id: 'new-message', type: 'start' }, freshSocket);
  h.close();
  assert.equal(h.states[1], true);
  h.receive({ id: 'new-message', type: 'message', data: 'Complete next answer' }, freshSocket);
  h.receive({ id: 'new-message', type: 'stop', data: [] }, freshSocket);
  assert.equal(h.states[1], false);
  assert.equal(h.states[0].at(-1).some(part => part.type === 'error'), false);
  assert.equal(h.renames.length, 1);
});

test('idle disconnect does not create a failed answer', () => {
  const h = chatHook();
  h.connectionError();
  h.close();
  assert.equal(h.states[1], false);
  assert.equal(h.states[0].length, 0);
});
