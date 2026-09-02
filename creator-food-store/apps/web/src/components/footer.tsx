import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-border bg-white">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="flex flex-col items-center justify-between gap-6 md:flex-row">
          <Link href="/" className="font-display text-2xl text-ink">
            GoodCart
          </Link>
          <nav className="flex flex-wrap justify-center gap-6 text-xs uppercase tracking-widest text-muted">
            <Link href="/discover" className="hover:text-ink">
              Discover
            </Link>
            <Link href="/signup?role=creator" className="hover:text-ink">
              For Creators
            </Link>
            <Link href="/terms" className="hover:text-ink">
              Terms
            </Link>
            <Link href="/privacy" className="hover:text-ink">
              Privacy
            </Link>
          </nav>
        </div>
        <p className="mt-8 text-center text-xs text-muted">
          Curated grocery, not the algorithm.
        </p>
      </div>
    </footer>
  );
}
