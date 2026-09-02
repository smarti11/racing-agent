import Link from "next/link";
import { auth, signOut } from "@/auth";
import { Button } from "@repo/ui";

export async function Navbar() {
  const session = await auth();
  const user = session?.user as { handle?: string; role?: string } | undefined;

  return (
    <header className="sticky top-0 z-50 border-b border-stone-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 font-bold text-emerald-700">
          <span className="text-2xl">🥗</span>
          <span>PantryLink</span>
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          <Link href="/discover" className="text-stone-600 hover:text-stone-900">
            Discover
          </Link>
          {user ? (
            <>
              <Link href="/locker" className="text-stone-600 hover:text-stone-900">
                My Locker
              </Link>
              {(user.role === "CREATOR" || user.role === "ADMIN") && (
                <Link href="/dashboard" className="text-stone-600 hover:text-stone-900">
                  Dashboard
                </Link>
              )}
              <Link href={`/@${user.handle}`} className="text-stone-600 hover:text-stone-900">
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
              <Link href="/login">
                <Button variant="ghost" size="sm">
                  Log in
                </Button>
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
