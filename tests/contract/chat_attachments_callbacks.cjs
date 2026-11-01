const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const cp = require('node:child_process');
const assert = require('node:assert/strict');
const test = require('node:test');
const ts = require('../../web/node_modules/typescript');
const lodash = require('../../web/node_modules/lodash');
const root = path.resolve(__dirname, '../..');
const directory = 'web/src/components/chat/';
const base = '0b86183eb023ee0094e0f370905cd5e73b4a2bff';
const read = (file, baseline) =>
  baseline
    ? cp.execFileSync('git', ['show', `${base}:${directory}${file}`], {
        cwd: root,
        encoding: 'utf8',
      })
    : fs.readFileSync(path.join(root, directory, file), 'utf8');
const json = (value) => JSON.parse(JSON.stringify(value));
function source(file, baseline) {
  return ts.createSourceFile(
    file,
    read(file, baseline),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
}
function bindingNames(name) {
  return ts.isIdentifier(name)
    ? [name.text]
    : name.elements.flatMap((e) => bindingNames(e.name));
}
// Only add a capture before the existing outer return. Callbacks and JSX execute unchanged.
function instrument(file, baseline) {
  const ast = source(file, baseline);
  const edits = [];
  function walk(node) {
    if (
      ts.isVariableDeclaration(node) &&
      ts.isIdentifier(node.name) &&
      /^(ChatInput|ChatMessages|useChatMessages|useChatAttachments)$/.test(
        node.name.text,
      )
    ) {
      const body = node.initializer.body;
      const names = body.statements
        .filter(ts.isVariableStatement)
        .flatMap((s) =>
          s.declarationList.declarations.flatMap((d) => bindingNames(d.name)),
        );
      const ret = body.statements.find(ts.isReturnStatement);
      edits.push([
        ret.getStart(ast),
        `globalThis.capture({${names.join(',')}});\n`,
      ]);
    }
    ts.forEachChild(node, walk);
  }
  walk(ast);
  let code = ast.text;
  for (const [offset, text] of edits.sort((a, b) => b[0] - a[0]))
    code = code.slice(0, offset) + text + code.slice(offset);
  return ts.transpileModule(code, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
      esModuleInterop: true,
    },
  }).outputText;
}
function runtime(file, baseline, overrides = {}) {
  const state = {
    slots: [],
    cursor: 0,
    effects: [],
    effectDeps: [],
    locals: {},
    tree: null,
    events: [],
    requests: [],
    uploads: [],
    statuses: [],
    urls: [],
    revoked: [],
    uuid: 0,
    ws: null,
    feedbackStatus: 200,
    failFeedback: false,
    upload: async () => ({ data: { id: 'doc-1' } }),
    documentStatus: 'COMPLETE',
    readyState: 1,
  };
  const chat = {
    id: 'chat-1',
    history: [[{ id: 'history', role: 'human', type: 'message', data: 'old' }]],
  };
  const props = {
    chat,
    welcome: false,
    loading: false,
    disabled: false,
    onSubmit: (data) => state.requests.push(json(data)),
    onCancel: () => state.events.push('cancel'),
    ...overrides,
  };
  const setState = (initial) => {
    const index = state.cursor++;
    if (!(index in state.slots))
      state.slots[index] = typeof initial === 'function' ? initial() : initial;
    return [
      state.slots[index],
      (value) => {
        state.slots[index] =
          typeof value === 'function' ? value(state.slots[index]) : value;
      },
    ];
  };
  const hooks = {
    useState: setState,
    useCallback: (f) => f,
    useMemo: (f) => f(),
    useRef: (initial) => {
      const [ref] = setState({ current: initial });
      return ref;
    },
    useEffect: (f, deps) => {
      const index = state.cursor++;
      const prev = state.effectDeps[index];
      if (!prev || deps.some((d, i) => !Object.is(d, prev[i])))
        state.effects.push(f);
      state.effectDeps[index] = deps;
    },
  };
  const toast = Object.fromEntries(
    ['error', 'info', 'success'].map((name) => [
      name,
      (...args) => state.events.push([name, ...json(args)]),
    ]),
  );
  const apiClient = {
    defaultApi: {
      botsBotIdChatsChatIdMessagesMessageIdPost: async (req) => {
        state.requests.push(json(req));
        if (state.failFeedback) throw Error('feedback failed');
        return { status: state.feedbackStatus };
      },
    },
    chatDocumentsApi: {
      chatsChatIdDocumentsPost: async (req) => {
        state.uploads.push(json(req));
        return state.upload(req);
      },
      chatsChatIdDocumentsDocumentIdGet: async (req) => {
        state.statuses.push(json(req));
        return { data: { status: state.documentStatus } };
      },
    },
  };
  class FixedDate extends Date {
    constructor(...args) {
      super(...(args.length ? args : [1700000000000]));
    }
    static now() {
      return 1700000000000;
    }
  }
  class FakeFile {
    constructor(parts, name, opts = {}) {
      Object.assign(this, {
        name,
        size: parts.reduce((n, p) => n + (p.size || String(p).length), 0),
        type: opts.type || '',
        lastModified: opts.lastModified || FixedDate.now(),
      });
    }
  }
  const cache = new Map();
  const ui = new Proxy({}, { get: (_, name) => String(name) });
  function load(filename) {
    if (cache.has(filename)) return cache.get(filename);
    const module = { exports: {} };
    cache.set(filename, module.exports);
    const customRequire = (name) => {
      if (name === 'react') return hooks;
      if (name === 'react/jsx-runtime')
        return {
          jsx: (type, props) => ({ type, props }),
          jsxs: (type, props) => ({ type, props }),
        };
      if (name === 'lodash') return lodash;
      if (name === 'next-intl')
        return {
          useLocale: () => 'zh-CN',
          useTranslations: () => (key) => key,
        };
      if (name === 'next/navigation')
        return { useParams: () => ({ botId: 'bot-1', chatId: 'chat-1' }) };
      if (name === 'ahooks')
        return {
          useWebSocket: (url, opts) => {
            state.ws = opts;
            state.wsUrl = url;
            return {
              readyState: state.readyState,
              sendMessage: (data) => state.requests.push(JSON.parse(data)),
              disconnect: () => state.events.push('disconnect'),
              connect: () => state.events.push('connect'),
            };
          },
        };
      if (name === 'ahooks/lib/useWebSocket')
        return { ReadyState: { Open: 1 } };
      if (name === 'react-scroll')
        return {
          animateScroll: {
            scrollToBottom: (opts) => state.events.push(['scroll', opts]),
          },
        };
      if (name === 'framer-motion') return { motion: ui };
      if (name === 'sonner') return { toast };
      if (name === 'use-local-storage-state')
        return { __esModule: true, default: () => setState(false) };
      if (name === '@/components/providers/bot-provider')
        return {
          useBotContext: () => ({
            mention: true,
            bot: {},
            collections: [
              { id: 'c1', title: 'One' },
              { id: 'c2', title: 'Two' },
            ],
            chatRename: (c) => state.events.push(['rename', c.id]),
          }),
        };
      if (name === '@/components/ui/sidebar')
        return { useSidebar: () => ({ open: true, isMobile: false }) };
      if (name === '@/lib/api/client') return { apiClient };
      if (name === '@/lib/utils')
        return { cn: (...args) => args.filter(Boolean).join(' ') };
      if (name.startsWith('./use-chat-')) return load(`${name.slice(2)}.ts`);
      return ui;
    };
    const context = {
      module,
      exports: module.exports,
      require: customRequire,
      capture: (values) => Object.assign(state.locals, values),
      process: { env: { NEXT_PUBLIC_BASE_PATH: '/sap' } },
      window: { location: { protocol: 'https:', host: 'sap.test' } },
      Date: FixedDate,
      File: FakeFile,
      crypto: { randomUUID: () => `uuid-${++state.uuid}` },
      URL: {
        createObjectURL: (file) => {
          const url = `blob:${state.urls.length + 1}`;
          state.urls.push([url, file.name]);
          return url;
        },
        revokeObjectURL: (url) => state.revoked.push(url),
      },
      console,
    };
    vm.runInNewContext(instrument(filename, baseline), context, { filename });
    return module.exports;
  }
  const component =
    load(file)[file === 'chat-input.tsx' ? 'ChatInput' : 'ChatMessages'];
  state.render = () => {
    state.cursor = 0;
    state.effects = [];
    state.locals = {};
    state.tree = component(props);
    return state.locals;
  };
  state.flush = async () => {
    const pending = state.effects.splice(0);
    for (const effect of pending) await effect();
    await new Promise((resolve) => setImmediate(resolve));
  };
  state.fragment = (data) =>
    state.ws.onMessage({
      data: typeof data === 'string' ? data : JSON.stringify(data),
    });
  state.makeFile = (name = 'image.png', type = 'image/png') =>
    new FakeFile(['image'], name, { type });
  state.props = props;
  state.render();
  return state;
}
function find(tree, type) {
  if (!tree || typeof tree !== 'object') return;
  if (tree.type === type) return tree;
  for (const child of Object.values(tree.props || {}).flat()) {
    const found = find(child, type);
    if (found) return found;
  }
}
const cases = {};
cases[
  'message stream, stop references, tool parts, turns, error and malformed JSON'
] = async (baseline) => {
  const s = runtime('chat-messages.tsx', baseline);
  await s.flush();
  assert.equal(
    s.wsUrl,
    'wss://sap.test/sap/api/v1/bots/bot-1/chats/chat-1/connect',
  );
  const f = (type, data, extra = {}) => {
    s.fragment({ id: 'a1', role: 'ai', type, data, ...extra });
    s.render();
  };
  f('start', '');
  f('message', 'hello');
  f('message', ' world');
  f('tool_call', 'first', { part_id: 'p1' });
  f('tool_call', '+second', { part_id: 'p1' });
  f('tool_call', 'other', { part_id: 'p2' });
  assert.equal(s.locals.loading, true);
  f('stop', [{ id: 'ref1', title: 'Reference' }], { skill_id: 'skill1' });
  assert.equal(s.locals.loading, false);
  assert.equal(s.locals.messages[1][1].data, 'hello world');
  assert.equal(s.locals.messages[1].filter((p) => p.type === 'stop').length, 1);
  assert.equal(
    s.locals.messages[1].find((p) => p.type === 'references').references[0].id,
    'ref1',
  );
  f('start', '', { id: 'a2' });
  f('error', 'problem', { id: 'error' });
  f('error', 'again', { id: 'error' });
  assert.equal(s.locals.loading, true);
  assert.throws(() => s.fragment('{broken'), /JSON|position|property/i);
  f('stop', 'not-array', { id: 'a2' });
  const before = json(s.locals.messages);
  s.props.chat = { id: 'changed', history: [] };
  s.render();
  assert.deepEqual(json(s.locals.messages), before);
  return json({
    messages: s.locals.messages,
    loading: s.locals.loading,
    events: s.events,
  });
};
cases[
  'send payload, FAQ action, feedback success/non-200/failure, cancel order and readyState'
] = async (baseline) => {
  const s = runtime('chat-messages.tsx', baseline);
  const payload = {
    query: '',
    files: [{ id: 'doc', name: 'file.png', previewUrl: 'blob:test' }],
    collections: [{ id: 'c1' }],
    completion: null,
    language: 'en',
    web_search_enabled: true,
  };
  s.locals.handleSendMessage(payload);
  s.render();
  assert.equal(s.locals.messages.at(-1)[0].data, ' ');
  s.locals.handleFaqChoice('faq-action', 'Label');
  s.render();
  s.fragment({ id: 'a1', role: 'ai', type: 'start', data: '' });
  s.fragment({ id: 'a1', role: 'ai', type: 'stop', data: [] });
  s.render();
  await s.locals.hanldeMessageFeedback({ id: 'a1' }, { type: 'like' });
  s.render();
  s.feedbackStatus = 400;
  await s.locals.hanldeMessageFeedback({ id: 'a1' }, { type: 'dislike' });
  s.render();
  s.failFeedback = true;
  await assert.rejects(
    s.locals.hanldeMessageFeedback({ id: 'a1' }, {}),
    /feedback failed/,
  );
  await s.locals.hanldeMessageFeedback({}, {});
  s.fragment({ id: 'a2', role: 'ai', type: 'start', data: '' });
  s.render();
  const count = s.events.length;
  s.locals.handleCancel();
  s.render();
  assert.deepEqual(s.events.slice(count), ['disconnect', 'connect']);
  assert.equal(s.locals.loading, false);
  const input = () => find(s.tree, 'ChatInput');
  assert.equal(input().props.disabled, false);
  s.readyState = 3;
  s.render();
  assert.equal(input().props.disabled, true);
  assert.deepEqual(s.requests[0], payload);
  assert.equal(s.requests[1].action, 'faq-action');
  return json({
    requests: s.requests,
    messages: s.locals.messages,
    events: s.events,
    disabled: input().props.disabled,
  });
};
function filesChange(s, files) {
  find(s.tree, 'FileUpload').props.onValueChange(files);
  s.render();
}
async function upload(s) {
  await s.locals.onAttachmentsChange();
  s.render();
}
cases[
  'attachment select, duplicate/single policy, upload, no polling, status and delete'
] = async (baseline) => {
  const s = runtime('chat-input.tsx', baseline);
  const file = s.makeFile('report.pdf', 'application/pdf');
  filesChange(s, [file, s.makeFile()]);
  assert.equal(s.locals.attachments.length, 1);
  assert.equal(s.locals.onFileValidate(file), '该文件已存在。');
  assert.equal(s.locals.onFileValidate(s.makeFile()), null);
  filesChange(s, [file]);
  await upload(s);
  await upload(s);
  assert.equal(s.uploads.length, 1);
  assert.equal(s.locals.attachments[0].progress_status, 'uploaded');
  await s.flush();
  assert.equal(s.statuses.length, 0);
  for (const [status, expected] of [
    ['PROCESSING', 'indexing'],
    ['FAILED', 'failed'],
    ['COMPLETE', 'success'],
  ]) {
    s.locals.setAttachments((items) => {
      items[0].progress_status = 'uploaded';
      return [...items];
    });
    s.render();
    s.documentStatus = status;
    await s.locals.checkAttachmentStatus();
    s.render();
    assert.equal(s.locals.attachments[0].progress_status, expected);
  }
  s.locals.onFileReject(file, 'too big');
  await s.locals.handleDeleteAttachment(s.locals.attachments[0]);
  s.render();
  assert.equal(s.locals.attachments.length, 0);
  return json({
    attachments: s.locals.attachments,
    uploads: s.uploads,
    statuses: s.statuses,
    events: s.events,
    urls: s.urls,
    revoked: s.revoked,
  });
};
cases[
  'image paste, preview replacement, existing attachment block and delete revoke'
] = async (baseline) => {
  const s = runtime('chat-input.tsx', baseline);
  let prevented = 0;
  const paste = () =>
    s.locals.handlePaste({
      clipboardData: {
        items: [
          { type: 'text/plain', getAsFile: () => null },
          { type: 'image/png', getAsFile: () => s.makeFile() },
          { type: 'image/jpeg', getAsFile: () => s.makeFile() },
        ],
      },
      preventDefault: () => prevented++,
    });
  paste();
  s.render();
  assert.equal(prevented, 1);
  assert.equal(s.locals.attachments.length, 1);
  assert.equal(s.urls.length, 1);
  paste();
  assert.equal(prevented, 1);
  await upload(s);
  assert.equal(s.urls.length, 2);
  assert.equal(s.locals.attachments[0].progress_status, 'success');
  await s.locals.handleDeleteAttachment(s.locals.attachments[0]);
  s.render();
  assert.deepEqual(s.revoked, ['blob:2']);
  s.locals.handlePaste({
    clipboardData: { items: [{ type: 'text/plain' }] },
    preventDefault: () => prevented++,
  });
  assert.equal(prevented, 1);
  return json({
    prevented,
    uploads: s.uploads,
    attachments: s.locals.attachments,
    events: s.events,
    urls: s.urls,
    revoked: s.revoked,
  });
};
cases['input guards, processing block, payload, send clear and submit throw'] =
  async (baseline) => {
    const s = runtime('chat-input.tsx', baseline);
    const snapshots = [];
    s.locals.handleSendMessage();
    assert.equal(s.requests.length, 0);
    s.locals.setQuery('  question  ');
    s.locals.setSelectedCollections(['c2']);
    s.locals.setWebSearchEnabled(true);
    s.render();
    for (const key of ['isComposing', 'mentionOpen']) {
      s.locals[key === 'isComposing' ? 'setIsComposing' : 'setMentionOpen'](
        true,
      );
      s.render();
      s.locals.handleSendMessage();
      s.locals[key === 'isComposing' ? 'setIsComposing' : 'setMentionOpen'](
        false,
      );
      s.render();
    }
    s.props.loading = true;
    s.render();
    s.locals.handleSendMessage();
    s.props.loading = false;
    s.render();
    assert.equal(s.requests.length, 0);
    filesChange(s, [s.makeFile()]);
    s.locals.handleSendMessage();
    assert.equal(s.requests.length, 0);
    await upload(s);
    s.props.onSubmit = (data) => {
      s.render();
      snapshots.push(
        json({
          data,
          query: s.locals.query,
          selectedCollections: s.locals.selectedCollections,
          attachments: s.locals.attachments,
        }),
      );
    };
    s.render();
    s.locals.handleSendMessage();
    s.render();
    assert.equal(snapshots[0].data.query, 'question');
    assert.equal(snapshots[0].query, '');
    assert.equal(snapshots[0].data.files[0].previewUrl, 'blob:1');
    s.locals.setQuery('failure');
    s.render();
    s.props.onSubmit = () => {
      throw Error('send failed');
    };
    s.render();
    assert.throws(() => s.locals.handleSendMessage(), /send failed/);
    s.render();
    assert.equal(s.locals.query, '');
    return json({
      snapshots,
      events: s.events,
      urls: s.urls,
      revoked: s.revoked,
      query: s.locals.query,
      attachments: s.locals.attachments,
    });
  };
cases[
  'upload failure, no automatic retry, missing id, remove before late response, absent chat id'
] = async (baseline) => {
  const observations = [];
  for (const mode of ['reject', 'no-id', 'late', 'no-chat']) {
    const s = runtime(
      'chat-input.tsx',
      baseline,
      mode === 'no-chat' ? { chat: {} } : {},
    );
    filesChange(s, [s.makeFile()]);
    if (mode === 'reject') {
      s.upload = async () => {
        throw Error('upload failed');
      };
      await assert.rejects(s.locals.onAttachmentsChange(), /upload failed/);
      await s.locals.onAttachmentsChange();
    }
    if (mode === 'no-id') {
      s.upload = async () => ({ data: {} });
      await upload(s);
      await upload(s);
    }
    if (mode === 'late') {
      let resolve;
      s.upload = () =>
        new Promise((r) => {
          resolve = r;
        });
      const pending = s.locals.onAttachmentsChange();
      await s.locals.handleDeleteAttachment(s.locals.attachments[0]);
      s.render();
      resolve({ data: { id: 'late-doc' } });
      await pending;
      s.render();
      assert.equal(s.locals.attachments.length, 0);
    }
    if (mode === 'no-chat') {
      await upload(s);
      assert.equal(s.uploads.length, 0);
    }
    s.render();
    observations.push(
      json({
        mode,
        attachments: s.locals.attachments,
        uploads: s.uploads,
        urls: s.urls,
        revoked: s.revoked,
      }),
    );
  }
  return observations;
};
function compact(node) {
  if (!node) return null;
  return [
    node.kind,
    node.getChildCount()
      ? node
          .getChildren()
          .filter((child) => child.kind !== ts.SyntaxKind.JSDocComment)
          .map(compact)
      : node.getText().replace(/\r\n/g, '\n'),
  ];
}
function declared(ast, name) {
  let found;
  function visit(n) {
    if (ts.isVariableDeclaration(n) && bindingNames(n.name).includes(name))
      found = n;
    ts.forEachChild(n, visit);
  }
  visit(ast);
  return found;
}
function outerReturn(ast, name) {
  return declared(ast, name).initializer.body.statements.find(
    ts.isReturnStatement,
  );
}
test('JSX, moved callback bodies and existing hook dependency arrays match fixed base', () => {
  const oldMessages = source('chat-messages.tsx', true),
    newMessages = source('chat-messages.tsx', false),
    messagesHook = source('use-chat-messages.ts', false);
  assert.deepEqual(
    compact(outerReturn(oldMessages, 'ChatMessages')),
    compact(outerReturn(newMessages, 'ChatMessages')),
  );
  for (const name of [
    'messages',
    'loading',
    'sendMessage',
    'handleSendMessage',
    'handleFaqChoice',
    'hanldeMessageFeedback',
    'handleCancel',
  ]) {
    assert.deepEqual(
      compact(declared(oldMessages, name)),
      compact(declared(messagesHook, name)),
      name,
    );
  }
  const oldBody = declared(oldMessages, 'ChatMessages').initializer.body
    .statements;
  const newBody = declared(messagesHook, 'useChatMessages').initializer.body
    .statements;
  assert.deepEqual(
    oldBody.filter((s) => !ts.isReturnStatement(s)).map(compact),
    newBody.filter((s) => !ts.isReturnStatement(s)).map(compact),
  );
  const oldInput = source('chat-input.tsx', true),
    newInput = source('chat-input.tsx', false),
    attachmentsHook = source('use-chat-attachments.ts', false);
  const oldJSX = outerReturn(oldInput, 'ChatInput').getText(oldInput);
  const newJSX = outerReturn(newInput, 'ChatInput').getText(newInput);
  const normalizedOld = oldJSX.replace(
    /onValueChange=\{\(files\) => \{[\s\S]*?\n                  \}\}/,
    'onValueChange={handleFilesChange}',
  );
  assert.deepEqual(
    compact(
      ts.createSourceFile(
        'jsx.tsx',
        normalizedOld,
        ts.ScriptTarget.Latest,
        true,
        ts.ScriptKind.TSX,
      ),
    ),
    compact(
      ts.createSourceFile(
        'jsx.tsx',
        newJSX,
        ts.ScriptTarget.Latest,
        true,
        ts.ScriptKind.TSX,
      ),
    ),
  );
  const oldSend = declared(oldInput, 'handleSendMessage').initializer;
  const newSend = declared(newInput, 'handleSendMessage').initializer;
  assert.deepEqual(
    compact(oldSend.arguments[0]),
    compact(newSend.arguments[0]),
  );
  assert.deepEqual(
    newSend.arguments[1].elements.map((e) => e.getText(newInput)),
    [
      ...oldSend.arguments[1].elements
        .map((e) => e.getText(oldInput))
        .slice(0, -1),
      'setAttachments',
      'webSearchEnabled',
    ],
  );
  for (const name of ['enabledCollections'])
    assert.deepEqual(
      compact(declared(oldInput, name)),
      compact(declared(newInput, name)),
      name,
    );
  for (const name of [
    'addFilesToAttachments',
    'handleDeleteAttachment',
    'onFileReject',
    'onFileValidate',
    'prevPendingIdsRef',
    'attachmentsRef',
    'checkAttachmentStatus',
    'onAttachmentsChange',
    'handlePaste',
    'isImageFile',
  ])
    assert.deepEqual(
      compact(declared(oldInput, name)),
      compact(declared(attachmentsHook, name)),
      name,
    );
  const originalSetup = declared(oldInput, 'ChatInput').initializer.body
    .statements;
  const attachmentStart = originalSetup.findIndex(
    (s) =>
      ts.isVariableStatement(s) &&
      s.declarationList.declarations.some((d) =>
        bindingNames(d.name).includes('attachments'),
      ),
  );
  const sendStart = originalSetup.findIndex(
    (s) =>
      ts.isVariableStatement(s) &&
      s.declarationList.declarations.some((d) =>
        bindingNames(d.name).includes('handleSendMessage'),
      ),
  );
  const originalAttachmentSetup = originalSetup.slice(
    attachmentStart,
    sendStart,
  );
  const movedSetup = declared(
    attachmentsHook,
    'useChatAttachments',
  ).initializer.body.statements.slice(0, originalAttachmentSetup.length);
  assert.deepEqual(
    originalAttachmentSetup.map(compact),
    movedSetup.map(compact),
  );
  let oldFileChange;
  function findFileChange(n) {
    if (
      ts.isJsxAttribute(n) &&
      n.name.getText(oldInput) === 'onValueChange' &&
      n.initializer &&
      ts.isJsxExpression(n.initializer) &&
      ts.isArrowFunction(n.initializer.expression) &&
      n.initializer.expression.parameters[0]?.name.getText(oldInput) === 'files'
    )
      oldFileChange = n.initializer.expression;
    ts.forEachChild(n, findFileChange);
  }
  findFileChange(oldInput);
  assert.ok(
    ts.isArrowFunction(
      declared(attachmentsHook, 'handleFilesChange').initializer,
    ),
    'preserve the original fresh callback identity',
  );
  assert.deepEqual(
    compact(oldFileChange.body),
    compact(declared(attachmentsHook, 'handleFilesChange').initializer.body),
  );
  function effects(ast) {
    const out = [];
    function walk(n) {
      if (ts.isCallExpression(n) && n.expression.getText(ast) === 'useEffect')
        out.push(compact(n));
      ts.forEachChild(n, walk);
    }
    walk(ast);
    return out;
  }
  assert.deepEqual(effects(oldInput), effects(attachmentsHook));
  assert.equal(
    (
      read('use-chat-attachments.ts', false).match(/checkAttachmentStatus/g) ||
      []
    ).length,
    1,
    'status checker stays unhooked',
  );
});
const report = { base, scenarios: {} };
for (const [name, run] of Object.entries(cases))
  test(name, async () => {
    const before = await run(true);
    const after = await run(false);
    assert.deepEqual(after, before);
    report.scenarios[name] = { before, after };
  });
test.after(() => {
  const out = path.join(root, '.run/chat-attachments');
  fs.mkdirSync(out, { recursive: true });
  fs.writeFileSync(
    path.join(out, 'observations.json'),
    JSON.stringify(report, null, 2) + '\n',
  );
});
