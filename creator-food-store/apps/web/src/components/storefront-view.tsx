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
}: {
  item: ProductItem;
  shortCode?: string;
}) {
  const appUrl = typeof window !== "undefined" ? window.location.origin : "";
  const shopUrl = shortCode ? `${appUrl}/go/${shortCode}` : "#";
  const commission = item.product.affiliateOffers[0]?.commissionRate;
  const saveProduct = trpc.consumer.saveProduct.useMutation();

  return (
    <div className="shopmy-card group flex flex-col">
      <div className="aspect-square overflow-hidden bg-cream">
        {item.product.imageUrl ? (
          <img
            src={item.product.imageUrl}
            alt={item.product.name}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full items-center justify-center font-display text-3xl text-muted">
            GC
          </div>
        )}
      </div>
      <div className="flex flex-1 flex-col p-5">
        {item.isPinned && <Badge variant="warning" className="mb-2 w-fit">Pinned</Badge>}
        {item.product.brand && (
          <p className="text-[10px] font-semibold uppercase tracking-widest text-muted">
            {item.product.brand}
          </p>
        )}
        <h3 className="mt-1 font-medium leading-snug text-ink line-clamp-2">
          {item.product.name}
        </h3>
        {item.note && (
          <p className="mt-2 text-sm italic text-muted">&ldquo;{item.note}&rdquo;</p>
        )}
        {item.product.priceCents && (
          <p className="mt-2 text-sm font-medium text-ink">
            ${(item.product.priceCents / 100).toFixed(2)}
          </p>
        )}
        {commission && (
          <p className="mt-1 text-[10px] uppercase tracking-wider text-muted">
            {(commission * 100).toFixed(0)}% commission
          </p>
        )}
        <div className="mt-4 flex gap-2">
          <a href={shopUrl} target="_blank" rel="noopener noreferrer sponsored" className="flex-1">
            <Button size="sm" className="w-full">
              Shop
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
    <div>
      {/* Creator header — ShopMy editorial profile */}
      <section className="border-b border-border bg-white px-6 py-16">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-8 text-center md:flex-row md:text-left">
          <div className="flex h-28 w-28 shrink-0 items-center justify-center overflow-hidden rounded-full bg-cream">
            {creator.avatarUrl ? (
              <img
                src={creator.avatarUrl}
                alt=""
                className="h-28 w-28 rounded-full object-cover"
              />
            ) : (
              <span className="font-display text-4xl text-ink">
                {creator.name?.[0] ?? "G"}
              </span>
            )}
          </div>
          <div className="flex-1">
            <p className="section-label">Curator</p>
            <h1 className="mt-1 font-display text-4xl text-ink">{creator.name}</h1>
            <p className="mt-1 text-sm uppercase tracking-widest text-muted">
              @{creator.handle}
            </p>
            {creator.bio && (
              <p className="mt-4 max-w-xl text-muted">{creator.bio}</p>
            )}
            <p className="mt-2 text-xs text-muted">
              {creator._count.followers} followers
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3 md:justify-start">
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
      </section>

      <div className="mx-auto max-w-6xl px-6 py-8">
        <AffiliateDisclosure className="border border-border bg-cream p-4 text-xs" />

        {creator.collections.map((collection) => (
          <section key={collection.id} className="mt-14">
            <p className="section-label">Collection</p>
            <h2 className="mt-1 font-display text-2xl text-ink">{collection.name}</h2>
            {collection.description && (
              <p className="mt-2 text-sm text-muted">{collection.description}</p>
            )}
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {collection.creatorProducts.map((item) => (
                <ProductCard
                  key={item.id}
                  item={item}
                  shortCode={linkMap[item.product.id]}
                />
              ))}
            </div>
          </section>
        ))}

        {creator.creatorProducts.length > 0 && (
          <section className="mt-14">
            <p className="section-label">All picks</p>
            <h2 className="mt-1 font-display text-2xl text-ink">Shop everything</h2>
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {creator.creatorProducts.map((item) => (
                <ProductCard
                  key={item.id}
                  item={item}
                  shortCode={linkMap[item.product.id]}
                />
              ))}
            </div>
          </section>
        )}

        {creator.creatorProducts.length === 0 && creator.collections.length === 0 && (
          <p className="mt-16 text-center text-muted">
            No products yet. Check back soon!
          </p>
        )}
      </div>
    </div>
  );
}
