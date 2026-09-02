"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from "@repo/ui";
import { Logo, LogoMark } from "@/components/logo";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
    });
    setLoading(false);
    if (result?.error) {
      setError("Invalid email or password");
    } else {
      router.push("/dashboard");
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-8rem)]">
      <div className="auth-panel">
        <Logo size="lg" className="[&_span]:text-white [&_span.text-brand]:text-brand-light [&_span.text-ink]:text-white" />
        <div>
          <h2 className="font-display text-3xl leading-tight">
            Welcome back to your curated cart
          </h2>
          <p className="mt-4 max-w-sm text-white/80">
            Sign in to follow creators, save products, and shop the grocery picks you love.
          </p>
        </div>
        <div className="flex items-center gap-3 text-sm text-white/60">
          <LogoMark size={32} />
          <span>Trusted by food creators everywhere</span>
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="mb-8 text-center lg:hidden">
            <Logo size="md" className="justify-center" />
          </div>
          <Card className="shadow-card">
            <CardHeader>
              <CardTitle>Welcome back</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="text-sm font-medium">Email</label>
                  <Input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Password</label>
                  <Input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
                {error && <p className="text-sm text-red-600">{error}</p>}
                <Button
                  type="submit"
                  className="w-full bg-brand hover:bg-brand-dark"
                  disabled={loading}
                >
                  {loading ? "Signing in..." : "Sign in"}
                </Button>
              </form>

              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-border" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-white px-2 text-muted">Or continue with</span>
                </div>
              </div>

              <div className="grid gap-2">
                <Button
                  variant="outline"
                  onClick={() => signIn("google", { callbackUrl: "/dashboard" })}
                >
                  Google
                </Button>
                <Button
                  variant="outline"
                  onClick={() => signIn("instagram", { callbackUrl: "/dashboard" })}
                >
                  Instagram
                </Button>
                <Button
                  variant="outline"
                  onClick={() => signIn("tiktok", { callbackUrl: "/dashboard" })}
                >
                  TikTok
                </Button>
              </div>

              <p className="text-center text-sm text-muted">
                Don&apos;t have an account?{" "}
                <Link href="/signup" className="text-brand underline">
                  Sign up
                </Link>
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
