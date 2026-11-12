import { AppHeader } from "@/components/AppHeader";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <AppHeader />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">{children}</main>
      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-4 text-xs text-slate-500 sm:px-6 lg:px-8">
          CreatorShield AI provides automated, heuristic guidance only. It is not legal advice, is not
          affiliated with YouTube, Google or Meta, and cannot guarantee any platform enforcement outcome.
        </div>
      </footer>
    </>
  );
}
