import { NextMiddleware, NextRequest, NextResponse } from 'next/server';
import { withApiProxy } from './middlewares/apiProxy';

type MiddlewareFactory = (next: NextMiddleware) => NextMiddleware;

export function withRootRedirect(next: NextMiddleware): NextMiddleware {
  return async (req: NextRequest, event) => {
    const { pathname } = req.nextUrl;
    // 如果是根路径，直接重定向到登录页
    if (pathname === '/') {
      const url = req.nextUrl.clone();
      url.pathname = '/auth/signin';
      return NextResponse.redirect(url);
    }
    return next(req, event);
  };
}

const stackMiddlewares = (
  functions: MiddlewareFactory[],
  index = 0,
): NextMiddleware => {
  const fn = functions[index];
  if (fn) {
    const next = stackMiddlewares(functions, index + 1);
    return fn(next);
  }
  return () => NextResponse.next();
};

// 把重定向放在最前面
export default stackMiddlewares([withRootRedirect, withApiProxy]);

// Routes Middleware should not run on
export const config = {
  matcher: ['/((?!static|_next|favicon.ico|robots.txt).*)'],
};
