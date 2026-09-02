"use client";

import { trpc } from "@/lib/trpc";
import { Badge, Button, Card, CardContent } from "@repo/ui";
import { useState } from "react";

export default function LockerPage() {
  const [alertPrice, setAlertPrice] = useState<Record<string, string>>({});
  const { data: locker, isLoading } = trpc.consumer.locker.useQuery();
  const { data: alerts } = trpc.consumer.priceAlerts.useQuery();
  const { data: feed } = trpc.consumer.feed.useQuery({ limit: 10 });

  const unsave = trpc.consumer.unsaveProduct.useMutation();
  const markPurchased = trpc.consumer.markPurchased.useMutation();
  const createAlert = trpc.consumer.createPriceAlert.useMutation();
  const cancelAlert = trpc.consumer.cancelPriceAlert.useMutation();
  const utils = trpc.useUtils();

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-3xl font-bold">My Locker</h1>
      <p className="mt-2 text-stone-600">Your saved food products and price alerts</p>

      {feed && feed.length > 0 && (
        <section className="mt-8">
          <h2 className="text-xl font-semibold">Feed from Creators You Follow</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {feed.map((item) => (
              <Card key={item.id}>
                <CardContent className="p-4">
                  <p className="text-xs text-stone-500">
                    @{item.creator.handle}
                  </p>
                  <h3 className="font-medium">{item.product.name}</h3>
                  {item.note && (
                    <p className="text-sm italic text-stone-600">{item.note}</p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      <section className="mt-8">
        <h2 className="text-xl font-semibold">Saved Products</h2>
        {isLoading && <p className="mt-4 text-stone-500">Loading...</p>}
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {locker?.map((saved) => (
            <Card key={saved.id}>
              <CardContent className="p-4">
                <div className="aspect-square rounded-lg bg-stone-100 flex items-center justify-center text-3xl">
                  {saved.product.imageUrl ? (
                    <img
                      src={saved.product.imageUrl}
                      alt=""
                      className="h-full w-full rounded-lg object-cover"
                    />
                  ) : (
                    "🍽️"
                  )}
                </div>
                <h3 className="mt-2 font-medium line-clamp-2">
                  {saved.product.name}
                </h3>
                {saved.product.priceCents && (
                  <p className="text-sm">
                    ${(saved.product.priceCents / 100).toFixed(2)}
                  </p>
                )}
                <div className="mt-2 flex flex-wrap gap-1">
                  {saved.isPurchased && <Badge variant="success">Purchased</Badge>}
                  {saved.isGifted && <Badge variant="info">Gifted</Badge>}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      markPurchased.mutate(
                        { productId: saved.productId, isPurchased: !saved.isPurchased },
                        { onSuccess: () => utils.consumer.locker.invalidate() }
                      )
                    }
                  >
                    {saved.isPurchased ? "Unmark" : "Purchased"}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      unsave.mutate(
                        { productId: saved.productId },
                        { onSuccess: () => utils.consumer.locker.invalidate() }
                      )
                    }
                  >
                    Remove
                  </Button>
                </div>
                <div className="mt-2 flex gap-1">
                  <input
                    type="number"
                    placeholder="Alert price $"
                    className="w-full rounded border px-2 py-1 text-sm"
                    value={alertPrice[saved.productId] ?? ""}
                    onChange={(e) =>
                      setAlertPrice({ ...alertPrice, [saved.productId]: e.target.value })
                    }
                  />
                  <Button
                    size="sm"
                    onClick={() => {
                      const cents = Math.round(
                        parseFloat(alertPrice[saved.productId] ?? "0") * 100
                      );
                      if (cents > 0) {
                        createAlert.mutate(
                          { productId: saved.productId, targetPriceCents: cents },
                          { onSuccess: () => utils.consumer.priceAlerts.invalidate() }
                        );
                      }
                    }}
                  >
                    Alert
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
        {locker?.length === 0 && (
          <p className="mt-4 text-stone-500">
            No saved products yet. Browse{" "}
            <a href="/discover" className="text-emerald-600 underline">
              Discover
            </a>{" "}
            to find products.
          </p>
        )}
      </section>

      {alerts && alerts.length > 0 && (
        <section className="mt-8">
          <h2 className="text-xl font-semibold">Price Alerts</h2>
          <div className="mt-4 space-y-2">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className="flex items-center justify-between rounded-lg border p-3"
              >
                <div>
                  <p className="font-medium">{alert.product.name}</p>
                  <p className="text-sm text-stone-500">
                    Alert when below ${(alert.targetPriceCents / 100).toFixed(2)}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    cancelAlert.mutate(
                      { alertId: alert.id },
                      { onSuccess: () => utils.consumer.priceAlerts.invalidate() }
                    )
                  }
                >
                  Cancel
                </Button>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
