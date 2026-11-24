"use client";

import Link from "next/link";
import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { Badge, Card, CardContent } from "@repo/ui";
import { GROCERY_CATEGORY_LABELS } from "@repo/affiliate-engine";
import { LogoMark } from "@/components/logo";

const CATEGORY_FILTERS = [
  { value: "", label: "All" },
  ...Object.entries(GROCERY_CATEGORY_LABELS).map(([value, label]) => ({
    value,
    label,
  })),
];

export default function DiscoverPage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string>("");

  const { data: discover } = trpc.catalog.discover.useQuery({ limit: 8 });
  const { data: searchResults } = trpc.catalog.search.useQuery({
    query: query || undefined,
    category: (category || undefined) as
      | "SNACKS"
      | "BEVERAGES"
      | "PANTRY"
      | "PRODUCE"
      | "DAIRY"
      | "FROZEN"
      | "DELI"
      | "BAKERY"
      | "MEAL_KITS"
      | "SUPPLEMENTS"
      | "SPECIALTY"
      | undefined,
    limit: 20,
  });

  return (
    <div>
      {/* Header band */}
      <section className="page-hero border-b border-border px-6 py-14">
        <div className="mx-auto max-w-6xl">
          <div className="flex items-start gap-4">
            <LogoMark size={48} className="hidden shrink-0 sm:block" />
            <div>
              <p className="section-label">Discover</p>
              <h1 className="mt-2 font-display text-4xl text-ink md:text-5xl">
                Shop the grocery aisle
              </h1>
              <p className="mt-3 max-w-2xl text-muted">
                Food, beverages, supplements, produce, dairy, frozen, deli, bakery, and
                every consumable product you&apos;d find at the store.
              </p>
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="flex flex-wrap gap-2">
          {CATEGORY_FILTERS.map((cat) => (
            <button
              key={cat.value || "all"}
              onClick={() => setCategory(cat.value)}
              className={`rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-wider transition-all ${
                category === cat.value
                  ? "bg-brand text-white shadow-card"
                  : "border border-border bg-white text-muted hover:border-brand hover:text-brand"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        <div className="relative mt-6">
          <input
            type="search"
            placeholder="Search snacks, drinks, supplements, produce..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full rounded-lg border border-border bg-white px-5 py-3.5 pl-12 text-sm shadow-card focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
          />
          <svg
            className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>

        <section className="mt-16">
          <h2 className="font-display text-2xl text-ink">Featured creators</h2>
          <p className="mt-1 text-sm text-muted">Follow tastemakers across every aisle</p>
          <div className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {discover?.featuredCreators.map((creator) => (
              <Link key={creator.id} href={`/@${creator.handle}`}>
                <Card className="shopmy-card group h-full overflow-hidden">
                  <div className="h-16 bg-brand-gradient" />
                  <CardContent className="relative p-5 pt-0">
                    <div className="-mt-8 flex h-16 w-16 items-center justify-center overflow-hidden rounded-full border-4 border-white bg-cream shadow-card">
                      {creator.avatarUrl ? (
                        <img
                          src={creator.avatarUrl}
                          alt=""
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <span className="font-display text-xl text-brand">
                          {creator.name?.[0] ?? "G"}
                        </span>
                      )}
                    </div>
                    <h3 className="mt-3 font-medium text-ink group-hover:text-brand">
                      {creator.name}
                    </h3>
                    <p className="text-xs uppercase tracking-wider text-muted">
                      @{creator.handle}
                    </p>
                    {creator.bio && (
                      <p className="mt-2 line-clamp-2 text-xs text-muted">{creator.bio}</p>
                    )}
                    <p className="mt-3 text-xs text-muted">
                      {creator._count.followers} followers · {creator._count.creatorProducts}{" "}
                      picks
                    </p>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </section>

        <section className="mt-16">
          <h2 className="font-display text-2xl text-ink">
            {query || category ? "Search results" : "Trending products"}
          </h2>
          <div className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {(query || category ? searchResults?.products : discover?.trendingProducts)?.map(
              (product) => (
                <Link key={product.id} href={`/products/${product.id}`}>
                  <Card className="shopmy-card group h-full overflow-hidden">
                    <div className="aspect-square overflow-hidden bg-cream">
                      {product.imageUrl ? (
                        <img
                          src={product.imageUrl}
                          alt={product.name}
                          className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                        />
                      ) : (
                        <div className="flex h-full items-center justify-center">
                          <LogoMark size={40} />
                        </div>
                      )}
                    </div>
                    <CardContent className="p-4">
                      <h3 className="line-clamp-2 text-sm font-medium text-ink group-hover:text-brand">
                        {product.name}
                      </h3>
                      {product.brand && (
                        <p className="mt-1 text-[10px] font-semibold uppercase tracking-wider text-muted">
                          {product.brand}
                        </p>
                      )}
                      <div className="mt-3 flex flex-wrap gap-1">
                        <Badge>
                          {GROCERY_CATEGORY_LABELS[
                            product.category as keyof typeof GROCERY_CATEGORY_LABELS
                          ] ?? product.category.replace("_", " ")}
                        </Badge>
                        {"_count" in product && (
                          <Badge variant="info">{product._count.creatorProducts} recs</Badge>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              )
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
