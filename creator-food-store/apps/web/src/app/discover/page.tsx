"use client";

import Link from "next/link";
import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { Badge, Card, CardContent } from "@repo/ui";

const CATEGORIES = [
  { value: "", label: "All" },
  { value: "SNACKS", label: "Snacks" },
  { value: "BEVERAGES", label: "Beverages" },
  { value: "PANTRY", label: "Pantry" },
  { value: "MEAL_KITS", label: "Meal Kits" },
  { value: "SUPPLEMENTS", label: "Supplements" },
  { value: "SPECIALTY", label: "Specialty" },
] as const;

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
      | "MEAL_KITS"
      | "SUPPLEMENTS"
      | "SPECIALTY"
      | "KITCHEN_TOOLS"
      | undefined,
    limit: 20,
  });

  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <p className="section-label">Discover</p>
      <h1 className="mt-2 font-display text-4xl text-ink">Shop by curator</h1>
      <p className="mt-3 max-w-xl text-muted">
        Trending food products and creators worth following
      </p>

      <div className="mt-8 flex flex-wrap gap-2">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.value}
            onClick={() => setCategory(cat.value)}
            className={`px-4 py-2 text-xs font-semibold uppercase tracking-wider transition-colors ${
              category === cat.value
                ? "bg-ink text-white"
                : "border border-border bg-white text-muted hover:border-ink hover:text-ink"
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      <input
        type="search"
        placeholder="Search food products..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="mt-6 w-full border border-border bg-white px-4 py-3 text-sm focus:border-ink focus:outline-none focus:ring-1 focus:ring-ink"
      />

      <section className="mt-16">
        <h2 className="font-display text-2xl text-ink">Featured creators</h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {discover?.featuredCreators.map((creator) => (
            <Link key={creator.id} href={`/@${creator.handle}`}>
              <Card className="shopmy-card group">
                <CardContent className="p-6">
                  <div className="flex h-14 w-14 items-center justify-center overflow-hidden rounded-full bg-cream">
                    {creator.avatarUrl ? (
                      <img
                        src={creator.avatarUrl}
                        alt=""
                        className="h-14 w-14 rounded-full object-cover"
                      />
                    ) : (
                      <span className="font-display text-xl text-ink">
                        {creator.name?.[0] ?? "G"}
                      </span>
                    )}
                  </div>
                  <h3 className="mt-4 font-medium text-ink group-hover:underline">
                    {creator.name}
                  </h3>
                  <p className="text-xs uppercase tracking-wider text-muted">
                    @{creator.handle}
                  </p>
                  <p className="mt-2 text-xs text-muted">
                    {creator._count.followers} followers ·{" "}
                    {creator._count.creatorProducts} picks
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
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {(query || category ? searchResults?.products : discover?.trendingProducts)?.map(
            (product) => (
              <Link key={product.id} href={`/products/${product.id}`}>
                <Card className="shopmy-card group">
                  <CardContent className="p-4">
                    <div className="flex aspect-square items-center justify-center overflow-hidden bg-cream">
                      {product.imageUrl ? (
                        <img
                          src={product.imageUrl}
                          alt={product.name}
                          className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                        />
                      ) : (
                        <span className="font-display text-3xl text-muted">GC</span>
                      )}
                    </div>
                    <h3 className="mt-4 line-clamp-2 text-sm font-medium text-ink">
                      {product.name}
                    </h3>
                    {product.brand && (
                      <p className="mt-1 text-xs uppercase tracking-wider text-muted">
                        {product.brand}
                      </p>
                    )}
                    <div className="mt-3 flex gap-1">
                      <Badge>{product.category.replace("_", " ")}</Badge>
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
  );
}
