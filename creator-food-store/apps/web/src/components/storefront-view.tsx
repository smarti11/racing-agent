"use client";

import Link from "next/link";
import { AffiliateDisclosure, Badge, Button } from "@repo/ui";
import { trpc } from "@/lib/trpc";

interface ProductItem {
  id: string;
  note: string | null;
  isPinned: boolean;
  product: {
    id: string;
    name: string;
    brand: string | null;
    imageUrl: string | null;
    category: string;
    priceCents: number | null;
    affiliateOffers: { commissionRate: number }[];
  };
}

interface Collection {
  id: string;
  name: string;
  description: string | null;
  creatorProducts: ProductItem[];
}

interface Creator {
  id: string;
  name: string | null;
  handle: string;
  bio: string | null;
  avatarUrl: string | null;
  instagramUrl: string | null;
  tiktokUrl: string | null;
  creatorProducts: ProductItem[];
  collections: Collection[];
  _count: { followers: number };
}

function ProductCard({
  item,
  shortCode,
  creatorId,
}: {
  item: ProductItem;
  shortCode?: string;
  creatorId: string;
}) {
  const appUrl = typeof window !== "undefined" ? window.location.origin : "";
  const shopUrl = shortCode ? `${appUrl}/go/${shortCode}` : "#";
  const commission = item.product.affiliateOffers[0]?.commissionRate;

  const saveProduct = trpc.consumer.saveProduct.useMutation();

  return (
    <div className="rounded-xl border bg-white p-4 transition hover:shadow-md">
      <div className="aspect-square rounded-lg bg-stone-100 flex items-center justify-center text-4xl overflow-hidden">
        {item.product.imageUrl ? (
          <img
            src={item.product.imageUrl}
            alt={item.product.name}
            className="h-full w-full object-cover"
          />
        ) : (
          "🍽️"
        )}
      </div>
      {item.isPinned && <Badge variant="warning" className="mt-2">Pinned</Badge>}
      <h3 className="mt-2 font-semibold line-clamp-2">{item.product.name}</h3>
      {item.product.brand && (
        <p className="text-sm text-stone-500">{item.product.brand}</p>
      )}
      {item.note && (
        <p className="mt-2 text-sm italic text-stone-600">&ldquo;{item.note}&rdquo;</p>
      )}
      {item.product.priceCents && (
        <p className="mt-1 text-sm font-medium">
          ${(item.product.priceCents / 100).toFixed(2)}
        </p>
      )}
      {commission && (
        <p className="text-xs text-emerald-600">
          {(commission * 100).toFixed(0)}% commission
        </p>
      )}
      <div className="mt-3 flex gap-2">
        <a href={shopUrl} target="_blank" rel="noopener noreferrer sponsored">
          <Button size="sm" className="w-full">
            Shop now
          </Button>
        </a>
        <Button
          size="sm"
          variant="outline"
          onClick={() => saveProduct.mutate({ productId: item.product.id })}
        >
          Save
        </Button>
      </div>
    </div>
  );
}

export function StorefrontView({
  creator,
  linkMap,
}: {
  creator: Creator;
  linkMap: Record<string, string>;
}) {
  const follow = trpc.consumer.follow.useMutation();
  const unfollow = trpc.consumer.unfollow.useMutation();
  const { data: isFollowing } = trpc.consumer.isFollowing.useQuery({
    creatorId: creator.id,
  });

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex flex-col items-center text-center sm:flex-row sm:text-left sm:items-start gap-6">
        <div className="flex h-24 w-24 items-center justify-center rounded-full bg-emerald-100 text-4xl">
          {creator.avatarUrl ? (
            <img
              src={creator.avatarUrl}
              alt=""
              className="h-24 w-24 rounded-full object-cover"
            />
          ) : (
            "👨‍🍳"
          )}
        </div>
        <div className="flex-1">
          <h1 className="text-3xl font-bold">{creator.name}</h1>
          <p className="text-stone-500">@{creator.handle}</p>
          {creator.bio && <p className="mt-2 text-stone-600">{creator.bio}</p>}
          <p className="mt-1 text-sm text-stone-400">
            {creator._count.followers} followers
          </p>
          <div className="mt-3 flex flex-wrap gap-2 justify-center sm:justify-start">
            {creator.instagramUrl && (
              <a href={creator.instagramUrl} target="_blank" rel="noopener noreferrer">
                <Badge>Instagram</Badge>
              </a>
            )}
            {creator.tiktokUrl && (
              <a href={creator.tiktokUrl} target="_blank" rel="noopener noreferrer">
                <Badge>TikTok</Badge>
              </a>
            )}
            <Button
              size="sm"
              variant={isFollowing ? "outline" : "primary"}
              onClick={() =>
                isFollowing
                  ? unfollow.mutate({ creatorId: creator.id })
                  : follow.mutate({ creatorId: creator.id })
              }
            >
              {isFollowing ? "Following" : "Follow"}
            </Button>
          </div>
        </div>
      </div>

      <AffiliateDisclosure className="mt-6 rounded-lg bg-stone-100 p-3" />

      {creator.collections.map((collection) => (
        <section key={collection.id} className="mt-10">
          <h2 className="text-xl font-semibold">{collection.name}</h2>
          {collection.description && (
            <p className="text-sm text-stone-500">{collection.description}</p>
          )}
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {collection.creatorProducts.map((item) => (
              <ProductCard
                key={item.id}
                item={item}
                shortCode={linkMap[item.product.id]}
                creatorId={creator.id}
              />
            ))}
          </div>
        </section>
      ))}

      {creator.creatorProducts.length > 0 && (
        <section className="mt-10">
          <h2 className="text-xl font-semibold">All Picks</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {creator.creatorProducts.map((item) => (
              <ProductCard
                key={item.id}
                item={item}
                shortCode={linkMap[item.product.id]}
                creatorId={creator.id}
              />
            ))}
          </div>
        </section>
      )}

      {creator.creatorProducts.length === 0 && creator.collections.length === 0 && (
        <p className="mt-10 text-center text-stone-500">
          No products yet. Check back soon!
        </p>
      )}
    </div>
  );
}
