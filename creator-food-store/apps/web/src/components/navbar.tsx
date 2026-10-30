import Link from "next/link";
import { auth, signOut } from "@/auth";
import { Button } from "@repo/ui";
import { Logo } from "@/components/logo";

export async function Navbar() {
  const session = await auth();
  const user = session?.user as { handle?: string; role?: string } | undefined;

  return (
    <header className="sticky top-0 z-50 border-b border-border/80 bg-white/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link href="/" className="transition-opacity hover:opacity-80">
          <Logo size="md" />
        </Link>
        <nav className="flex items-center gap-5 text-xs font-medium uppercase tracking-widest">
          <Link href="/discover" className="text-muted transition-colors hover:text-brand">
            Discover
          </Link>
          {user ? (
            <>
              <Link href="/locker" className="text-muted transition-colors hover:text-brand">
                My Cart
              </Link>
              {(user.role === "CREATOR" || user.role === "ADMIN") && (
                <Link href="/dashboard" className="text-muted transition-colors hover:text-brand">
                  Dashboard
                </Link>
              )}
              <Link
                href={`/@${user.handle}`}
                className="text-muted transition-colors hover:text-brand"
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
              <Link href="/login" className="text-muted transition-colors hover:text-brand">
                Log in
              </Link>
              <Link href="/signup">
                <Button size="sm" className="bg-brand hover:bg-brand-dark">
                  Sign up
                </Button>
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
