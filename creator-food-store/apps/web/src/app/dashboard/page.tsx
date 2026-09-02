"use client";

import { useState } from "react";
import Link from "next/link";
import { trpc } from "@/lib/trpc";
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Badge } from "@repo/ui";

export default function DashboardPage() {
  const [productUrl, setProductUrl] = useState("");
  const [note, setNote] = useState("");
  const [newCollectionName, setNewCollectionName] = useState("");

  const utils = trpc.useUtils();
  const { data: analytics, isLoading: analyticsLoading } =
    trpc.analytics.dashboard.useQuery({ days: 30 });
  const { data: collections } = trpc.collections.list.useQuery();
  const { data: stripeStatus } = trpc.stripe.getOnboardingStatus.useQuery();

  const addProduct = trpc.storefront.addProduct.useMutation({
    onSuccess: () => {
      setProductUrl("");
      setNote("");
      utils.analytics.dashboard.invalidate();
    },
  });

  const createCollection = trpc.collections.create.useMutation({
    onSuccess: () => {
      setNewCollectionName("");
      utils.collections.list.invalidate();
    },
  });

  const removeProduct = trpc.storefront.removeProduct.useMutation({
    onSuccess: () => utils.analytics.dashboard.invalidate(),
  });

  async function connectStripe() {
    const res = await fetch("/api/stripe/connect", { method: "POST" });
    const data = await res.json();
    if (data.url) window.location.href = data.url;
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Creator Dashboard</h1>
        <Link href="/dashboard/settings">
          <Button variant="outline" size="sm">
            Settings
          </Button>
        </Link>
      </div>

      {!stripeStatus?.stripeOnboarded && (
        <Card className="mt-6 border-amber-200 bg-amber-50">
          <CardContent className="flex items-center justify-between p-4">
            <div>
              <p className="font-medium">Connect Stripe to receive payouts</p>
              <p className="text-sm text-stone-600">
                Set up your payout account to get paid weekly.
              </p>
            </div>
            <Button onClick={connectStripe}>Connect Stripe</Button>
          </CardContent>
        </Card>
      )}

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Clicks (30d)", value: analytics?.totalClicks ?? 0 },
          {
            label: "Conversion Rate",
            value: `${(analytics?.conversionRate ?? 0).toFixed(1)}%`,
          },
          {
            label: "Confirmed Earnings",
            value: `$${(analytics?.confirmedCommission ?? 0).toFixed(2)}`,
          },
          {
            label: "Pending Payout",
            value: `$${(analytics?.pendingEarnings ?? 0).toFixed(2)}`,
          },
        ].map((stat) => (
          <Card key={stat.label}>
            <CardContent className="p-4">
              <p className="text-sm text-stone-500">{stat.label}</p>
              <p className="text-2xl font-bold">
                {analyticsLoading ? "..." : stat.value}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Add a Product</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium">Product URL</label>
              <Input
                placeholder="https://www.amazon.com/dp/..."
                value={productUrl}
                onChange={(e) => setProductUrl(e.target.value)}
              />
            </div>
            <div>
              <label className="text-sm font-medium">Your note (optional)</label>
              <Input
                placeholder="Why you love this product..."
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </div>
            <Button
              onClick={() =>
                addProduct.mutate({ url: productUrl, note: note || undefined })
              }
              disabled={!productUrl || addProduct.isPending}
            >
              {addProduct.isPending ? "Adding..." : "Add & Monetize"}
            </Button>
            {addProduct.error && (
              <p className="text-sm text-red-600">{addProduct.error.message}</p>
            )}
            {addProduct.data && (
              <div className="rounded-lg bg-emerald-50 p-3 text-sm">
                <p className="font-medium text-emerald-800">Product added!</p>
                <p className="text-emerald-700">
                  Tracked link: {addProduct.data.trackedLink}
                </p>
                <p className="text-emerald-600">
                  Commission: {(addProduct.data.commissionRate * 100).toFixed(0)}%
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Collections</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                placeholder="New collection name"
                value={newCollectionName}
                onChange={(e) => setNewCollectionName(e.target.value)}
              />
              <Button
                onClick={() =>
                  createCollection.mutate({ name: newCollectionName })
                }
                disabled={!newCollectionName}
              >
                Add
              </Button>
            </div>
            <ul className="space-y-2">
              {collections?.map((col) => (
                <li
                  key={col.id}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div>
                    <p className="font-medium">{col.name}</p>
                    <p className="text-xs text-stone-500">
                      {col._count.creatorProducts} products · {col.visibility}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      {analytics?.topProducts && analytics.topProducts.length > 0 && (
        <Card className="mt-8">
          <CardHeader>
            <CardTitle>Top Products</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {analytics.topProducts.map((tp, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between border-b pb-2 last:border-0"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-stone-400">#{i + 1}</span>
                    <div>
                      <p className="font-medium">{tp.product?.name ?? "Unknown"}</p>
                      <p className="text-xs text-stone-500">
                        {tp.conversions} conversions
                      </p>
                    </div>
                  </div>
                  <p className="font-medium text-emerald-600">
                    ${tp.commission.toFixed(2)}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {analytics?.recentConversions && analytics.recentConversions.length > 0 && (
        <Card className="mt-8">
          <CardHeader>
            <CardTitle>Recent Conversions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {analytics.recentConversions.map((conv) => (
                <div
                  key={conv.id}
                  className="flex items-center justify-between text-sm"
                >
                  <span>{conv.product.name}</span>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        conv.status === "CONFIRMED" ? "success" : "warning"
                      }
                    >
                      {conv.status}
                    </Badge>
                    <span className="font-medium">
                      ${conv.commission.toFixed(2)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {analytics?.payouts && analytics.payouts.length > 0 && (
        <Card className="mt-8">
          <CardHeader>
            <CardTitle>Payout History</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {analytics.payouts.map((payout) => (
                <div
                  key={payout.id}
                  className="flex items-center justify-between text-sm"
                >
                  <span>
                    {new Date(payout.periodStart).toLocaleDateString()} –{" "}
                    {new Date(payout.periodEnd).toLocaleDateString()}
                  </span>
                  <div className="flex items-center gap-2">
                    <Badge variant={payout.status === "PAID" ? "success" : "info"}>
                      {payout.status}
                    </Badge>
                    <span className="font-medium">${payout.amount.toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
