"use client";

import Link from "next/link";
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

import { useState } from "react";

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
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-3xl font-bold">Discover</h1>
      <p className="mt-2 text-stone-600">
        Trending food products and top creators
      </p>

      <div className="mt-6 flex flex-wrap gap-2">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.value}
            onClick={() => setCategory(cat.value)}
            className={`rounded-full px-4 py-1.5 text-sm ${
              category === cat.value
                ? "bg-emerald-600 text-white"
                : "bg-stone-100 text-stone-700 hover:bg-stone-200"
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
        className="mt-4 w-full rounded-lg border border-stone-300 px-4 py-2"
      />

      <section className="mt-10">
        <h2 className="text-xl font-semibold">Featured Creators</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {discover?.featuredCreators.map((creator) => (
            <Link key={creator.id} href={`/@${creator.handle}`}>
              <Card className="transition hover:shadow-md">
                <CardContent className="p-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-xl">
                    {creator.avatarUrl ? (
                      <img
                        src={creator.avatarUrl}
                        alt=""
                        className="h-12 w-12 rounded-full object-cover"
                      />
                    ) : (
                      "👨‍🍳"
                    )}
                  </div>
                  <h3 className="mt-3 font-semibold">{creator.name}</h3>
                  <p className="text-sm text-stone-500">@{creator.handle}</p>
                  <p className="mt-1 text-xs text-stone-400">
                    {creator._count.followers} followers ·{" "}
                    {creator._count.creatorProducts} picks
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-xl font-semibold">
          {query || category ? "Search Results" : "Trending Products"}
        </h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {(query || category ? searchResults?.products : discover?.trendingProducts)?.map(
            (product) => (
              <Link key={product.id} href={`/products/${product.id}`}>
                <Card className="transition hover:shadow-md">
                  <CardContent className="p-4">
                    <div className="aspect-square rounded-lg bg-stone-100 flex items-center justify-center text-4xl">
                      {product.imageUrl ? (
                        <img
                          src={product.imageUrl}
                          alt={product.name}
                          className="h-full w-full rounded-lg object-cover"
                        />
                      ) : (
                        "🍽️"
                      )}
                    </div>
                    <h3 className="mt-3 line-clamp-2 text-sm font-semibold">
                      {product.name}
                    </h3>
                    {product.brand && (
                      <p className="text-xs text-stone-500">{product.brand}</p>
                    )}
                    <div className="mt-2 flex gap-1">
                      <Badge variant="info">{product.category.replace("_", " ")}</Badge>
                      {"_count" in product && (
                        <Badge>{product._count.creatorProducts} recs</Badge>
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
