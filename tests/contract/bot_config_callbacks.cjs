const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('../../web/node_modules/typescript');
const root = path.resolve(__dirname, '../..');
const zod = require('../../web/node_modules/zod');
const resolver = require('../../web/node_modules/@hookform/resolvers/zod');
const flow = {
  version: '1',
  viewport: { x: 30, y: 40, zoom: 1.4 },
  nodes: [
    {
      id: 'start',
      type: 'action',
      position: { x: 0, y: 0 },
      data: { prompt: 'keep' },
    },
  ],
  edges: [
    {
      id: 'edge',
      source: 'start',
      target: 'start',
      type: 'step',
      sourceHandle: 'yes',
      data: { keep: true },
    },
  ],
};
const skill = (id) => ({
  id,
  name: id,
  description: 'existing',
  enabled: true,
  type: 'workflow',
  category: 'operations',
  runtime: {
    provider: 'test',
    model: 'test',
    temperature: 0.4,
    max_tokens: 256,
    top_p: 0.63,
    timeout_ms: 1717,
  },
  prompts: { skill_prompt: 'test' },
  tools: [
    {
      tool_id: 'search',
      enabled: true,
      required: true,
      timeout_ms: 818,
      retry_count: 3,
    },
  ],
  io: { input_schema: { x: 'string' }, output_schema: {} },
  flow,
  collections: [{ id: 'test-collection' }],
  meta: { owner: 'test' },
});
const defaultBot = {
  id: 'test-bot',
  title: 'test',
  description: '',
  type: 'agent',
  is_default: false,
  is_protected: true,
  config: {
    agent: {
      completion: {
        model: 'test',
        model_service_provider: 'test',
        custom_llm_provider: 'test',
        temperature: 0.2,
        max_tokens: 454,
        timeout: 17,
        tags: ['existing'],
      },
      collections: [{ id: 'test-collection' }],
      welcome_title: 'Welcome',
      welcome_subtitle: 'test',
      system_prompt_template: 'system',
      query_prompt_template: 'query',
    },
    flow: {
      name: 'keep-flow',
      title: 'Keep flow',
      version: '1',
      nodes: [],
      edges: [],
    },
    orchestration: {
      skills: [skill('one'), skill('two')],
      intent_router: {
        id: 'main',
        name: 'router',
        description: '',
        enabled: true,
        mode: 'llm',
        llm: {
          provider: 'test',
          model: 'test',
          temperature: 0,
          max_tokens: 128,
          top_p: 0.78,
          timeout_ms: 1919,
        },
        prompt_template: 'test',
        confidence_threshold: 0.6,
        fallback_skill_id: 'two',
        candidate_skills: [
          {
            skill_id: 'one',
            label: 'one',
            description: 'existing',
            enabled: true,
            examples: ['first'],
          },
          {
            skill_id: 'two',
            label: 'two',
            description: 'existing',
            enabled: true,
            examples: ['second'],
          },
        ],
        rules: [],
        flow,
        meta: { owner: 'test' },
      },
    },
  },
};
const input = process.argv[2]
  ? JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
  : {};
const baseline = input.bot || defaultBot;
function render(file, exportName, overrides = {}, options = {}) {
  const state = {
    bot: structuredClone(options.bot || baseline),
    requests: [],
    success: [],
    errors: [],
    loads: 0,
    pushes: [],
    refreshes: 0,
    events: [],
    fail: false,
    failLoad: false,
    form: null,
  };
  const cache = new Map();
  const noop = () => {};
  const ui = new Proxy({}, { get: (_, k) => k });
  const hooks = {
    useCallback: (f) => f,
    useMemo: (f) => f(),
    useEffect: noop,
    useRef: (v) => ({ current: v }),
    useState: (v) => [typeof v === 'function' ? v() : v, noop],
  };
  const jsx = {
    Fragment: 'Fragment',
    jsx: (type, props) =>
      typeof type === 'function' ? type(props) : { type, props },
    jsxs: (type, props) =>
      typeof type === 'function' ? type(props) : { type, props },
  };
  const apiClient = {
    defaultApi: {
      botsBotIdPut: async (req) => {
        state.events.push('put');
        if (state.fail) throw Error('request failed');
        state.requests.push(structuredClone(req));
        return { data: req.botUpdate };
      },
    },
  };
  function load(filename) {
    if (cache.has(filename)) return cache.get(filename);
    const m = { exports: {} };
    cache.set(filename, m.exports);
    const customRequire = (name) => {
      if (name === 'react') return hooks;
      if (name === 'react/jsx-runtime') return jsx;
      if (name === 'reactflow')
        return {
          default: 'ReactFlow',
          Position: { Top: 'top', Bottom: 'bottom' },
          MarkerType: { ArrowClosed: 'closed' },
        };
      if (name.endsWith('.css')) return {};
      if (name === 'lodash') return require('../../web/node_modules/lodash');
      if (name === 'zod') return zod;
      if (name === '@hookform/resolvers/zod') return resolver;
      if (name === 'react-hook-form')
        return {
          useWatch: () => '',
          useForm: (opts) => {
            const values = Object.assign(
              structuredClone(opts.defaultValues),
              overrides,
            );
            state.form = { values, opts };
            return {
              control: {},
              watch: (n) => values[n],
              getValues: () => values,
              reset: noop,
              setValue: (n, v) => {
                values[n] = v;
              },
              handleSubmit: (callback) => async () => {
                const result = await opts.resolver(
                  values,
                  {},
                  {
                    shouldUseNativeValidation: false,
                    criteriaMode: 'firstError',
                  },
                );
                state.validationErrors = result.errors;
                if (!Object.keys(result.errors).length)
                  return callback(result.values);
              },
            };
          },
        };
      if (name === 'next-intl')
        return { useTranslations: () => (k) => k, useMessages: () => ({}) };
      if (name === 'next/navigation')
        return {
          useRouter: () => ({
            push: (value) => {
              state.pushes.push(value);
              state.events.push('push');
            },
            refresh: () => {
              state.refreshes++;
              state.events.push('refresh');
            },
          }),
        };
      if (name === 'sonner')
        return {
          toast: {
            success: (v) => {
              state.success.push(v);
              state.events.push('success');
            },
            error: (v) => state.errors.push(v),
          },
        };
      if (name === '@/components/providers/bot-config-provider')
        return {
          useBotConfigContext: () => ({
            bot: state.bot,
            loadBot: async () => {
              state.events.push('load');
              state.loads++;
              if (state.failLoad) throw Error('refresh failed');
            },
          }),
        };
      if (name === '@/lib/api/client') return { apiClient };
      if (name.startsWith('@/components/') || name === 'lucide-react')
        return ui;
      if (
        [
          'flow-utils',
          'bot-config-updater',
          'use-skill-editor',
          'skill-config',
        ].some((moduleName) => name.endsWith(moduleName))
      )
        return load(path.resolve(path.dirname(filename), name + '.ts'));
      if (name.endsWith('skill-editor-fields'))
        return load(path.resolve(path.dirname(filename), name + '.tsx'));
      if (name.startsWith('.')) return ui;
      return ui;
    };
    const out = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2020,
        jsx: ts.JsxEmit.ReactJSX,
        esModuleInterop: true,
      },
    }).outputText;
    vm.runInThisContext('(function(require,module,exports){' + out + '\n})', {
      filename,
    })(customRequire, m, m.exports);
    cache.set(filename, m.exports);
    return m.exports;
  }
  const mod = load(path.join(root, 'web/src/app/workspace/bots/[botId]', file));
  state.tree = mod[exportName](options.props || { skillId: 'one' });
  return state;
}
function find(tree, pred) {
  if (!tree || typeof tree !== 'object') return;
  if (pred(tree)) return tree;
  for (const child of [tree.props?.children].flat(Infinity)) {
    const found = find(child, pred);
    if (found) return found;
  }
}
const routes = [
  ['bot-form.tsx', 'BotForm', 'bot'],
  ['intent-router/intent-router-editor.tsx', 'IntentRouterEditor', 'intent'],
  ['skills/skill-editor.tsx', 'SkillEditor', 'normal'],
  ['skills/skill-editor.tsx', 'SkillEditor', 'quick'],
];
// Execute real component save callbacks and Zod resolvers. Hooks, presentation
// components and the API transport are local substitutes; this is not browser/DB E2E.
(async () => {
  const captures = [];
  const actionFor = (state, kind) =>
    kind === 'quick'
      ? () =>
          find(
            state.tree,
            (n) => typeof n.props?.onQuickSave === 'function',
          ).props.onQuickSave(structuredClone(flow))
      : () => find(state.tree, (n) => n.type === 'form').props.onSubmit();
  for (const [file, name, kind] of routes) {
    const state = render(file, name);
    const savedResult = await actionFor(state, kind)();
    assert.equal(
      state.requests.length,
      1,
      JSON.stringify(state.validationErrors),
    );
    const actual = state.requests[0].botUpdate.config;
    if (kind === 'bot') {
      assert.deepEqual(
        actual.agent.collections,
        baseline.config.agent.collections,
      );
      assert.deepEqual(
        actual.agent.completion,
        baseline.config.agent.completion,
      );
      assert.deepEqual(actual.orchestration, baseline.config.orchestration);
    } else if (kind === 'intent') {
      assert.deepEqual(
        actual.orchestration.intent_router.llm,
        baseline.config.orchestration.intent_router.llm,
      );
      assert.deepEqual(
        actual.orchestration.skills,
        baseline.config.orchestration.skills,
      );
    } else {
      const previous = baseline.config.orchestration.skills[0];
      assert.equal(actual.orchestration.skills[0].category, previous.category);
      assert.deepEqual(
        actual.orchestration.skills[0].runtime,
        previous.runtime,
      );
      assert.deepEqual(actual.orchestration.skills[0].tools, previous.tools);
      assert.deepEqual(actual.orchestration.skills[0].io, previous.io);
      assert.deepEqual(actual.agent, baseline.config.agent);
      const { candidate_skills, fallback_skill_id, ...savedRouter } =
        actual.orchestration.intent_router;
      const {
        candidate_skills: previousCandidates,
        fallback_skill_id: previousFallback,
        ...previousRouter
      } = baseline.config.orchestration.intent_router;
      assert.deepEqual(savedRouter, previousRouter);
    }
    assert.deepEqual(
      actual.orchestration.skills[1],
      baseline.config.orchestration.skills[1],
    );
    assert.equal(actual.orchestration.intent_router.fallback_skill_id, 'two');
    assert.deepEqual(
      actual.orchestration.intent_router.candidate_skills,
      baseline.config.orchestration.intent_router.candidate_skills,
    );
    assert.deepEqual(actual.flow, baseline.config.flow);
    if (kind === 'normal' || kind === 'quick') {
      assert.equal(state.loads, 1);
      assert.deepEqual(
        state.pushes,
        kind === 'normal' ? [`/workspace/bots/${baseline.id}/skills`] : [],
      );
      assert.equal(state.refreshes, kind === 'normal' ? 1 : 0);
      assert.deepEqual(
        state.success,
        kind === 'normal' ? ['update_success'] : [],
      );
      assert.deepEqual(
        state.events,
        kind === 'normal'
          ? ['put', 'load', 'success', 'push', 'refresh']
          : ['put', 'load'],
      );
      if (kind === 'quick') assert.equal(savedResult, true);
    }
    captures.push({ kind, request: state.requests[0] });

    const failed = render(file, name);
    failed.fail = true;
    await assert.rejects(actionFor(failed, kind), /request failed/);
    assert.equal(failed.loads, 0);
    assert.equal(failed.success.length, 0);
    assert.equal(failed.requests.length, 0);
    assert.deepEqual(failed.pushes, []);
    assert.equal(failed.refreshes, 0);
  }
  // Ordinary Zod coercion and quick getValues retain their different payloads.
  for (const kind of ['normal', 'quick']) {
    const state = render('skills/skill-editor.tsx', 'SkillEditor', {
      temperature: '0.8',
      max_tokens: '1024',
    });
    await actionFor(state, kind)();
    const runtime =
      state.requests[0].botUpdate.config.orchestration.skills[0].runtime;
    assert.equal(runtime.temperature, kind === 'normal' ? 0.8 : '0.8');
    assert.equal(runtime.max_tokens, kind === 'normal' ? 1024 : '1024');
  }
  // A failed Provider refresh also stops the success/navigation path.
  for (const kind of ['normal', 'quick']) {
    const failedRefresh = render('skills/skill-editor.tsx', 'SkillEditor');
    failedRefresh.failLoad = true;
    await assert.rejects(actionFor(failedRefresh, kind), /refresh failed/);
    assert.equal(failedRefresh.requests.length, 1);
    assert.equal(failedRefresh.loads, 1);
    assert.deepEqual(failedRefresh.success, []);
    assert.deepEqual(failedRefresh.pushes, []);
    assert.equal(failedRefresh.refreshes, 0);
  }
  // Explicit edits replace selected arrays/text; preservation does not resurrect removals.
  for (const kind of ['normal', 'quick']) {
    const state = render('skills/skill-editor.tsx', 'SkillEditor', {
      tools: [],
      collections: [],
      skill_prompt: '',
      description: '',
    });
    await actionFor(state, kind)();
    const saved = state.requests[0].botUpdate.config.orchestration.skills[0];
    assert.deepEqual(saved.tools, []);
    assert.deepEqual(saved.collections, []);
    assert.equal(saved.prompts.skill_prompt, '');
    assert.equal(saved.description, '');
    captures.push({ kind: kind + '-clear', request: state.requests[0] });
  }
  // Existing quick-save bypasses form validation and the ordinary fallback guard.
  const invalid = render('skills/skill-editor.tsx', 'SkillEditor', {
    name: '',
  });
  await actionFor(invalid, 'normal')();
  assert.equal(invalid.requests.length, 0);
  const quick = render('skills/skill-editor.tsx', 'SkillEditor', { name: '' });
  await actionFor(quick, 'quick')();
  assert.equal(quick.requests.length, 1);
  const conflict = render('skills/skill-editor.tsx', 'SkillEditor', {
    is_fallback: true,
  });
  await actionFor(conflict, 'normal')();
  assert.equal(conflict.requests.length, 0);
  assert.deepEqual(conflict.errors, ['only_one_fallback_skill_error']);
  const quickConflict = render('skills/skill-editor.tsx', 'SkillEditor', {
    is_fallback: true,
  });
  await actionFor(quickConflict, 'quick')();
  assert.equal(
    quickConflict.requests[0].botUpdate.config.orchestration.intent_router
      .fallback_skill_id,
    'one',
  );

  for (const kind of ['normal', 'quick']) {
    const duplicateBot = structuredClone(baseline);
    duplicateBot.config.orchestration.skills.push(
      structuredClone(duplicateBot.config.orchestration.skills[0]),
    );
    const duplicate = render(
      'skills/skill-editor.tsx',
      'SkillEditor',
      {},
      { bot: duplicateBot },
    );
    await actionFor(duplicate, kind)();
    assert.equal(
      duplicate.requests[0].botUpdate.config.orchestration.skills.length,
      kind === 'normal' ? 2 : 3,
    );
  }

  // The canvas itself must retain accepted layout/edge metadata when it builds a save.
  let canvasSaved;
  const canvas = render(
    'flow-canvas-editor.tsx',
    'FlowCanvasEditor',
    {},
    {
      props: {
        title: 'test',
        description: '',
        value: flow,
        onChange: () => {},
        onQuickSave: async (v) => {
          canvasSaved = v;
          return true;
        },
      },
    },
  );
  const saveButton = find(
    canvas.tree,
    (n) => n.type === 'Button' && n.props?.children === 'save_bot',
  );
  await saveButton.props.onClick();
  assert.deepEqual(canvasSaved.viewport, flow.viewport);
  assert.equal(canvasSaved.edges[0].type, 'step');
  assert.deepEqual(canvasSaved.nodes, flow.nodes);
  assert.deepEqual(canvasSaved.edges[0].data, { keep: true });
  const failedCanvas = render(
    'flow-canvas-editor.tsx',
    'FlowCanvasEditor',
    {},
    {
      props: {
        title: 'test',
        description: '',
        value: flow,
        onChange: () => {},
        onQuickSave: async () => {
          throw Error('request failed');
        },
      },
    },
  );
  await find(
    failedCanvas.tree,
    (n) => n.type === 'Button' && n.props?.children === 'save_bot',
  ).props.onClick();
  assert.deepEqual(failedCanvas.success, []);
  assert.deepEqual(failedCanvas.errors, ['flow_canvas_save_failed']);

  process.stdout.write(JSON.stringify({ bot: baseline, captures }) + '\n');
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
