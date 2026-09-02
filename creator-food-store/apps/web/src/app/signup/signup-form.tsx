"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from "@repo/ui";
import { trpc } from "@/lib/trpc";
import { Logo, LogoMark } from "@/components/logo";

export default function SignupForm({
  defaultRole = "CONSUMER",
}: {
  defaultRole?: "CREATOR" | "CONSUMER";
}) {
  const router = useRouter();

  const [form, setForm] = useState({
    email: "",
    password: "",
    name: "",
    handle: "",
    role: defaultRole as "CREATOR" | "CONSUMER",
  });
  const [error, setError] = useState("");

  const register = trpc.auth.register.useMutation({
    onSuccess: async () => {
      await signIn("credentials", {
        email: form.email,
        password: form.password,
        redirect: false,
      });
      router.push(form.role === "CREATOR" ? "/dashboard" : "/discover");
    },
    onError: (err) => setError(err.message),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    register.mutate(form);
  }

  return (
    <div className="flex min-h-[calc(100vh-8rem)]">
      <div className="auth-panel">
        <Logo size="lg" className="[&_span]:text-white [&_span.text-brand]:text-brand-light [&_span.text-ink]:text-white" />
        <div>
          <h2 className="font-display text-3xl leading-tight">
            {form.role === "CREATOR"
              ? "Share what you love, earn what you deserve"
              : "Discover grocery picks from creators you trust"}
          </h2>
          <p className="mt-4 max-w-sm text-white/80">
            Join GoodCart — the creator commerce platform for every consumable aisle.
          </p>
        </div>
        <div className="flex items-center gap-3 text-sm text-white/60">
          <LogoMark size={32} />
          <span>Free to join · Start in minutes</span>
        </div>
      </div>

      <div className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <div className="mb-8 text-center lg:hidden">
            <Logo size="md" className="justify-center" />
          </div>
          <Card className="shadow-card">
            <CardHeader>
              <CardTitle>Create your account</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant={form.role === "CREATOR" ? "primary" : "outline"}
                  className={`flex-1 ${form.role === "CREATOR" ? "bg-brand hover:bg-brand-dark" : ""}`}
                  onClick={() => setForm({ ...form, role: "CREATOR" })}
                >
                  I&apos;m a creator
                </Button>
                <Button
                  type="button"
                  variant={form.role === "CONSUMER" ? "primary" : "outline"}
                  className={`flex-1 ${form.role === "CONSUMER" ? "bg-brand hover:bg-brand-dark" : ""}`}
                  onClick={() => setForm({ ...form, role: "CONSUMER" })}
                >
                  I&apos;m a shopper
                </Button>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="text-sm font-medium">Name</label>
                  <Input
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Handle</label>
                  <div className="flex items-center gap-1">
                    <span className="text-muted">@</span>
                    <Input
                      value={form.handle}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          handle: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""),
                        })
                      }
                      required
                      pattern="[a-z0-9_]{3,30}"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium">Email</label>
                  <Input
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Password</label>
                  <Input
                    type="password"
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    required
                    minLength={8}
                  />
                </div>
                {error && <p className="text-sm text-red-600">{error}</p>}
                <Button
                  type="submit"
                  className="w-full bg-brand hover:bg-brand-dark"
                  disabled={register.isPending}
                >
                  {register.isPending ? "Creating..." : "Create account"}
                </Button>
              </form>

              <p className="text-center text-xs text-muted">
                By signing up you agree to our{" "}
                <Link href="/terms" className="text-brand underline">
                  Terms
                </Link>{" "}
                and{" "}
                <Link href="/privacy" className="text-brand underline">
                  Privacy Policy
                </Link>
                .
              </p>

              <p className="text-center text-sm text-muted">
                Already have an account?{" "}
                <Link href="/login" className="text-brand underline">
                  Log in
                </Link>
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
