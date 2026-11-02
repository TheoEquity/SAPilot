import { AppLocaleDropdownMenu } from '@/components/app-topbar';
import { AppLogo } from '@/components/app-topbar';
import Image from 'next/image';

export default async function AuthLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      {/* Left panel - Branding */}
      <div className="relative hidden bg-gradient-to-br from-[#1e3a5f] to-[#0f2440] lg:flex lg:flex-col lg:items-center lg:justify-center">
        {/* Background geometric shapes */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-24 -left-24 h-96 w-96 rounded-full bg-white/5 blur-3xl"></div>
          <div className="absolute -bottom-24 -right-24 h-96 w-96 rounded-full bg-blue-500/10 blur-3xl"></div>
        </div>

        {/* Branding content */}
        <div className="relative z-10 flex flex-col items-center gap-8 px-12 text-center">
          <div className="relative h-64 w-64">
            <Image
              src="/sapilot-main.png"
              alt="SAPilot"
              fill
              className="object-contain"
              priority
            />
          </div>
          <div className="flex flex-col gap-2">
            <h1 className="text-3xl font-bold text-white">SAP 运维领航员</h1>
            <p className="text-white/70 text-lg">SAP Operations AI Agent Platform</p>
          </div>
        </div>
      </div>

      {/* Right panel - Auth forms */}
      <div className="relative flex min-h-svh flex-col items-center justify-center gap-6 p-6 md:p-10">
        {/* Locale switcher - top right */}
        <div className="absolute right-4 top-4">
          <AppLocaleDropdownMenu />
        </div>

        <div className="flex w-full max-w-sm flex-col gap-6">
          {/* Mobile logo */}
          <div className="self-center lg:hidden">
            <AppLogo />
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
