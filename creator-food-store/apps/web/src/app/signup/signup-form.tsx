"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from "@repo/ui";
import { trpc } from "@/lib/trpc";

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
    <div className="mx-auto max-w-md px-4 py-12">
      <Card>
        <CardHeader>
          <CardTitle>Create your account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Button
              type="button"
              variant={form.role === "CREATOR" ? "primary" : "outline"}
              className="flex-1"
              onClick={() => setForm({ ...form, role: "CREATOR" })}
            >
              I&apos;m a creator
            </Button>
            <Button
              type="button"
              variant={form.role === "CONSUMER" ? "primary" : "outline"}
              className="flex-1"
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
                <span className="text-stone-400">@</span>
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
            <Button type="submit" className="w-full" disabled={register.isPending}>
              {register.isPending ? "Creating..." : "Create account"}
            </Button>
          </form>

          <p className="text-center text-xs text-stone-500">
            By signing up you agree to our{" "}
            <Link href="/terms" className="underline">
              Terms
            </Link>{" "}
            and{" "}
            <Link href="/privacy" className="underline">
              Privacy Policy
            </Link>
            .
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
