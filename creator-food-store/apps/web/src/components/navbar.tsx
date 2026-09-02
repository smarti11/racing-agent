import Link from "next/link";
import { auth, signOut } from "@/auth";
import { Button } from "@repo/ui";

export async function Navbar() {
  const session = await auth();
  const user = session?.user as { handle?: string; role?: string } | undefined;

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-white/95 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link href="/" className="font-display text-2xl tracking-tight text-ink">
          GoodCart
        </Link>
        <nav className="flex items-center gap-6 text-xs font-medium uppercase tracking-widest">
          <Link href="/discover" className="text-muted transition-colors hover:text-ink">
            Discover
          </Link>
          {user ? (
            <>
              <Link href="/locker" className="text-muted transition-colors hover:text-ink">
                My Cart
              </Link>
              {(user.role === "CREATOR" || user.role === "ADMIN") && (
                <Link href="/dashboard" className="text-muted transition-colors hover:text-ink">
                  Dashboard
                </Link>
              )}
              <Link
                href={`/@${user.handle}`}
                className="text-muted transition-colors hover:text-ink"
              >
                Profile
              </Link>
              <form
                action={async () => {
                  "use server";
                  await signOut({ redirectTo: "/" });
                }}
              >
                <Button type="submit" variant="ghost" size="sm">
                  Sign out
                </Button>
              </form>
            </>
          ) : (
            <>
              <Link href="/login" className="text-muted transition-colors hover:text-ink">
                Log in
              </Link>
              <Link href="/signup">
                <Button size="sm">Sign up</Button>
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
