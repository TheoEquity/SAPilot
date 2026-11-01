import { getResponse, HttpResponse } from 'msw';
import { createServer } from 'node:http';
import { createMockHandlers, type MockScenario } from './handlers';

/** Local HTTP transport for generated MSW handlers. Never forwards to a backend. */
export function createMockServer(scenario: MockScenario = 'default') {
  const handlers = createMockHandlers(scenario);
  const server = createServer(async (incoming, outgoing) => {
    let response: Response;
    try {
      const chunks: Buffer[] = [];
      for await (const chunk of incoming) chunks.push(Buffer.from(chunk));
      const body = Buffer.concat(chunks);
      const headers = new Headers();
      for (const [key, value] of Object.entries(incoming.headers)) {
        if (value !== undefined)
          headers.set(key, Array.isArray(value) ? value.join(', ') : value);
      }
      const request = new Request(
        `http://${incoming.headers.host}${incoming.url}`,
        {
          method: incoming.method,
          headers,
          ...(body.length ? { body: new Uint8Array(body).buffer } : {}),
        },
      );
      response =
        (await getResponse(handlers, request)) ??
        HttpResponse.json(
          {
            detail: `No generated Mock handler for ${request.method} ${new URL(request.url).pathname}`,
          },
          { status: 501 },
        );
    } catch (error) {
      response =
        error instanceof Response
          ? error
          : HttpResponse.json(
              { detail: 'Mock request failed' },
              { status: 500 },
            );
    }
    outgoing.writeHead(response.status, Object.fromEntries(response.headers));
    outgoing.end(Buffer.from(await response.arrayBuffer()));
  });
  server.on('upgrade', (_request, socket) => {
    socket.end(
      'HTTP/1.1 501 Not Implemented\r\nConnection: close\r\nContent-Length: 0\r\n\r\n',
    );
  });
  return server;
}
