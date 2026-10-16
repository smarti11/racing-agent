"use client";

import { trpc } from "@/lib/trpc";
import { Badge, Button, Card, CardContent } from "@repo/ui";

export default function AdminPage() {
  const { data: stats } = trpc.admin.stats.useQuery();
  const { data: queue } = trpc.admin.moderationQueue.useQuery();
  const approve = trpc.admin.approveProduct.useMutation();
  const reject = trpc.admin.rejectProduct.useMutation();
  const utils = trpc.useUtils();

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-3xl font-bold">Admin Panel</h1>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {[
          { label: "Total Users", value: stats?.users ?? 0 },
          { label: "Creators", value: stats?.creators ?? 0 },
          { label: "Products", value: stats?.products ?? 0 },
          { label: "Conversions", value: stats?.conversions ?? 0 },
          { label: "GMV", value: `$${(stats?.gmv ?? 0).toFixed(0)}` },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="p-4">
              <p className="text-sm text-stone-500">{s.label}</p>
              <p className="text-2xl font-bold">{s.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <section className="mt-10">
        <h2 className="text-xl font-semibold">Moderation Queue</h2>
        <div className="mt-4 space-y-2">
          {queue?.length === 0 && (
            <p className="text-stone-500">No items pending review.</p>
          )}
          {queue?.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between rounded-lg border p-4"
            >
              <div>
                <p className="font-medium">Product: {item.productId}</p>
                <p className="text-sm text-stone-500">{item.reason}</p>
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={() =>
                    item.productId &&
                    approve.mutate(
                      { productId: item.productId },
                      { onSuccess: () => utils.admin.moderationQueue.invalidate() }
                    )
                  }
                >
                  Approve
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  onClick={() =>
                    item.productId &&
                    reject.mutate(
                      { productId: item.productId, reason: "Non-consumable product" },
                      { onSuccess: () => utils.admin.moderationQueue.invalidate() }
                    )
                  }
                >
                  Reject
                </Button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
