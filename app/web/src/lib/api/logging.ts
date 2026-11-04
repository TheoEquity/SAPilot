import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios';
import { logger } from '../logger';

/** Attach once to each existing transport; never log config, headers or bodies. */
export function attachRequestLogging(client: AxiosInstance) {
  const started = new WeakMap<object, number>();
  client.interceptors.request.use((config) => {
    started.set(config, performance.now());
    return config;
  });
  const summary = (config?: AxiosRequestConfig) => ({
    method: config?.method?.toUpperCase(),
    path: config?.url,
    duration_ms:
      config && started.has(config)
        ? Math.round(performance.now() - started.get(config)!)
        : undefined,
  });
  client.interceptors.response.use(
    (response) => {
      const log =
        response.config.method?.toLowerCase() === 'get'
          ? logger.debug
          : logger.info;
      log('http.request.completed', {
        ...summary(response.config),
        status: 'success',
        status_code: response.status,
        trace_id: response.headers['x-trace-id'],
      });
      return response;
    },
    (error: unknown) => {
      const detail = axios.isAxiosError(error) ? error : undefined;
      const cancelled = axios.isCancel(error);
      const status = detail?.response?.status;
      const log = cancelled
        ? logger.info
        : status === undefined || status >= 500
          ? logger.error
          : logger.warn;
      log(cancelled ? 'http.request.cancelled' : 'http.request.failed', {
        ...summary(detail?.config),
        status: cancelled ? 'cancelled' : 'failed',
        status_code: detail?.response?.status,
        trace_id: detail?.response?.headers['x-trace-id'],
        error_code: detail?.code,
        error,
      });
      return Promise.reject(error);
    },
  );
}
