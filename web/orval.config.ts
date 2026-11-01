import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { defineConfig } from 'orval';

export default defineConfig({
  api: {
    hooks: {
      afterAllFilesWrite: () => {
        // Orval 8.45 also indexes empty Faker files for schema-less responses.
        // Keep its generated index valid without hand-editing generated files.
        const index = resolve('src/api/generated/index.faker.ts');
        const lines = readFileSync(index, 'utf8').split('\n');
        const exports = lines.filter((line) => {
          const target = line.match(/from ['"](.+)['"]/)?.[1];
          return (
            !target ||
            /^export\s/m.test(
              readFileSync(resolve(dirname(index), `${target}.ts`), 'utf8'),
            )
          );
        });
        writeFileSync(index, exports.join('\n'));
      },
    },
    input: {
      target: '../.run/openapi/openapi.json',
      override: {
        // Application transports already supply /api/v1 as their base URL.
        // Keep the exported documentation's full paths unchanged.
        transformer: (document) => ({
          ...document,
          paths: Object.fromEntries(
            Object.entries(document.paths || {})
              .filter(([path]) => path.startsWith('/api/v1/'))
              .map(([path, operation]) => [
                path.slice('/api/v1'.length),
                operation,
              ]),
          ),
        }),
      },
    },
    output: {
      target: './src/api/generated/endpoints.ts',
      schemas: './src/api/generated/models',
      client: 'axios',
      mode: 'tags-split',
      clean: false,
      mock: {
        indexMockFiles: true,
        generators: [
          {
            type: 'msw',
            baseUrl: '*/api/v1',
            delay: false,
            useExamples: true,
          },
          { type: 'faker', useExamples: true },
        ],
      },
      override: {
        useDates: false,
      },
    },
  },
});
