import { defineConfig } from 'orval';

export default defineConfig({
  api: {
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
      override: {
        useDates: false,
      },
    },
  },
});
