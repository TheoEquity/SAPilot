type Level = 'debug' | 'info' | 'warn' | 'error';
type Field =
  | 'stage'
  | 'status'
  | 'duration_ms'
  | 'status_code'
  | 'method'
  | 'path'
  | 'trace_id'
  | 'document_id'
  | 'message_id'
  | 'chat_id'
  | 'collection_id'
  | 'error_type'
  | 'error_code'
  | 'file_count'
  | 'size'
  | 'close_code';
export type LogFields = Partial<Record<Field, string | number | boolean>> & {
  error?: unknown;
};

const fields: Field[] = [
  'stage',
  'status',
  'duration_ms',
  'status_code',
  'method',
  'path',
  'trace_id',
  'document_id',
  'message_id',
  'chat_id',
  'collection_id',
  'error_type',
  'error_code',
  'file_count',
  'size',
  'close_code',
];

function write(level: Level, event: string, data: LogFields = {}) {
  try {
    if (level === 'debug' && process.env.NODE_ENV !== 'development') return;
    // Event names are code-owned identifiers, never user input or error text.
    if (!/^[a-z][a-z0-9_.]{0,100}$/.test(event)) return;
    const record: Record<string, unknown> = {
      timestamp: new Date().toISOString(),
      level: level === 'warn' ? 'WARNING' : level.toUpperCase(),
      service: typeof window === 'undefined' ? 'frontend-server' : 'browser',
      event,
    };
    for (const key of fields) {
      const value = data[key];
      if (typeof value === 'number' && Number.isFinite(value))
        record[key] = value;
      else if (typeof value === 'boolean') record[key] = value;
      else if (typeof value === 'string') {
        if (key === 'path')
          record[key] = new URL(value, 'http://logger.local').pathname.slice(
            0,
            200,
          );
        else if (key === 'trace_id') {
          if (/^[a-f0-9]{32}$/i.test(value)) record[key] = value;
        } else if (/^[a-zA-Z0-9_.:-]{1,128}$/.test(value)) record[key] = value;
      }
    }
    if (data.error instanceof Error && /^[\w.]{1,64}$/.test(data.error.name)) {
      record.error_type = data.error.name;
    }
    console[level](JSON.stringify(record));
  } catch {
    // Logging must never replace a business result or recurse on output errors.
  }
}

export const logger = {
  debug: (event: string, fields?: LogFields) => write('debug', event, fields),
  info: (event: string, fields?: LogFields) => write('info', event, fields),
  warn: (event: string, fields?: LogFields) => write('warn', event, fields),
  error: (event: string, fields?: LogFields) => write('error', event, fields),
};
