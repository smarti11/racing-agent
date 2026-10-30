"use client";

import { trpc } from "@/lib/trpc";
import { Button, Card, CardContent, Input } from "@repo/ui";
import { useState } from "react";

export default function SettingsPage() {
  const { data: profile } = trpc.profile.getByHandle.useQuery(
    { handle: "" },
    { enabled: false }
  );
  const updateProfile = trpc.profile.update.useMutation();
  const becomeCreator = trpc.profile.becomeCreator.useMutation();

  const [form, setForm] = useState({
    name: "",
    bio: "",
    instagramUrl: "",
    tiktokUrl: "",
  });

  return (
    <div className="mx-auto max-w-lg px-4 py-8">
      <h1 className="text-2xl font-bold">Profile Settings</h1>
      <Card className="mt-6">
        <CardContent className="space-y-4 p-6">
          <div>
            <label className="text-sm font-medium">Display Name</label>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div>
            <label className="text-sm font-medium">Bio</label>
            <Input
              value={form.bio}
              onChange={(e) => setForm({ ...form, bio: e.target.value })}
            />
          </div>
          <div>
            <label className="text-sm font-medium">Instagram URL</label>
            <Input
              value={form.instagramUrl}
              onChange={(e) => setForm({ ...form, instagramUrl: e.target.value })}
              placeholder="https://instagram.com/yourhandle"
            />
          </div>
          <div>
            <label className="text-sm font-medium">TikTok URL</label>
            <Input
              value={form.tiktokUrl}
              onChange={(e) => setForm({ ...form, tiktokUrl: e.target.value })}
              placeholder="https://tiktok.com/@yourhandle"
            />
          </div>
          <Button
            onClick={() => updateProfile.mutate(form)}
            disabled={updateProfile.isPending}
          >
            Save Changes
          </Button>
          <Button
            variant="outline"
            onClick={() => becomeCreator.mutate()}
            disabled={becomeCreator.isPending}
          >
            Become a Creator
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
