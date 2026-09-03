import Link from "next/link";
import { Logo } from "@/components/logo";

export function Footer() {
  return (
    <footer className="border-t border-border bg-white">
      <div className="mx-auto max-w-6xl px-6 py-14">
        <div className="flex flex-col items-center justify-between gap-8 md:flex-row md:items-start">
          <div className="text-center md:text-left">
            <Link href="/" className="inline-block transition-opacity hover:opacity-80">
              <Logo size="md" />
            </Link>
            <p className="mt-4 max-w-xs text-sm text-muted">
              Curated grocery from creators you trust — every aisle, one cart.
            </p>
          </div>
          <nav className="flex flex-wrap justify-center gap-x-8 gap-y-3 text-xs uppercase tracking-widest text-muted">
            <Link href="/discover" className="transition-colors hover:text-brand">
              Discover
            </Link>
            <Link href="/signup?role=creator" className="transition-colors hover:text-brand">
              For Creators
            </Link>
            <Link href="/terms" className="transition-colors hover:text-brand">
              Terms
            </Link>
            <Link href="/privacy" className="transition-colors hover:text-brand">
              Privacy
            </Link>
          </nav>
        </div>
        <div className="mt-10 flex flex-col items-center justify-between gap-4 border-t border-border pt-8 md:flex-row">
          <p className="text-xs text-muted">
            © {new Date().getFullYear()} GoodCart. All rights reserved.
          </p>
          <p className="text-xs text-muted">
            Curated grocery, not the algorithm.
          </p>
        </div>
      </div>
    </footer>
  );
}
