import { NextResponse } from 'next/server';
import { withApiProxy } from './middlewares/apiProxy';

export default withApiProxy(() => NextResponse.next());

// Routes Middleware should not run on
export const config = {
  matcher: ['/((?!static|_next|favicon.ico|robots.txt).*)'],
};
