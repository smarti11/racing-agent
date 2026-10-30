import Link from "next/link";
import { Button } from "@repo/ui";
import { prisma } from "@repo/db";
import { Logo, LogoMark } from "@/components/logo";

const COLLECTION_PREVIEWS = [
  {
    title: "Morning Routine",
    desc: "Coffee, oats, supplements — start strong",
    image: "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=600&h=400&fit=crop",
    href: "/@grocerygirl",
  },
  {
    title: "Snack Attack",
    desc: "Bars, chips, and guilt-free treats",
    image: "https://images.unsplash.com/photo-1621939514649-280e2ee25f60?w=600&h=400&fit=crop",
    href: "/discover?category=SNACKS",
  },
  {
    title: "Wellness Shelf",
    desc: "Vitamins, protein, greens & more",
    image: "https://images.unsplash.com/photo-1550572017-edd951aa8b74?w=600&h=400&fit=crop",
    href: "/@fitfuel",
  },
];

async function getFeaturedData() {
  const [creators, products] = await Promise.all([
    prisma.user.findMany({
      where: { role: "CREATOR" },
      take: 3,
      orderBy: { creatorProducts: { _count: "desc" } },
      select: {
        id: true,
        name: true,
        handle: true,
        bio: true,
        avatarUrl: true,
        _count: { select: { followers: true, creatorProducts: true } },
      },
    }),
    prisma.product.findMany({
      where: { isApproved: true, category: { not: "KITCHEN_TOOLS" } },
      take: 4,
      orderBy: { creatorProducts: { _count: "desc" } },
      select: {
        id: true,
        name: true,
        brand: true,
        imageUrl: true,
        priceCents: true,
      },
    }),
  ]);
  return { creators, products };
}

export default async function HomePage() {
  const { creators, products } = await getFeaturedData();

  return (
    <div>
      {/* Hero */}
      <section className="page-hero px-6 py-20 md:py-28">
        <div className="mx-auto max-w-5xl text-center">
          <div className="flex justify-center">
            <LogoMark size={72} className="shadow-card-hover" />
          </div>
          <p className="brand-pill mt-8">Curated grocery, not the algorithm</p>
          <h1 className="mt-6 font-display text-4xl leading-tight text-ink md:text-6xl md:leading-[1.08]">
            Shop every aisle from creators you actually trust
          </h1>
          <p className="mx-auto mt-8 max-w-2xl text-lg leading-relaxed text-muted">
            GoodCart is for every consumable you&apos;d grab at the store — snacks,
            beverages, supplements, produce, dairy, frozen, deli, bakery, and pantry
            staples. Creators earn when you shop their picks.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link href="/signup?role=creator">
              <Button size="lg" className="bg-brand hover:bg-brand-dark">
                Start your storefront
              </Button>
            </Link>
            <Link href="/discover">
              <Button variant="outline" size="lg">
                Explore creators
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Featured creators */}
      {creators.length > 0 && (
        <section className="border-t border-border bg-cream px-6 py-20">
          <div className="mx-auto max-w-6xl">
            <p className="section-label">Shop by Creator</p>
            <h2 className="mt-3 font-display text-3xl text-ink md:text-4xl">
              Insider access to your favorite food tastemakers
            </h2>
            <div className="mt-10 grid gap-6 md:grid-cols-3">
              {creators.map((creator) => (
                <Link key={creator.id} href={`/@${creator.handle}`} className="group">
                  <article className="shopmy-card overflow-hidden">
                    <div className="h-32 bg-brand-gradient opacity-90 transition-opacity group-hover:opacity-100" />
                    <div className="relative px-6 pb-6">
                      <div className="-mt-10 flex h-20 w-20 items-center justify-center overflow-hidden rounded-full border-4 border-white bg-cream shadow-card">
                        {creator.avatarUrl ? (
                          <img
                            src={creator.avatarUrl}
                            alt=""
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <span className="font-display text-2xl text-brand">
                            {creator.name?.[0] ?? "G"}
                          </span>
                        )}
                      </div>
                      <h3 className="mt-4 font-display text-xl text-ink group-hover:text-brand">
                        {creator.name}
                      </h3>
                      <p className="text-xs uppercase tracking-wider text-muted">
                        @{creator.handle}
                      </p>
                      {creator.bio && (
                        <p className="mt-2 line-clamp-2 text-sm text-muted">{creator.bio}</p>
                      )}
                      <p className="mt-3 text-xs text-muted">
                        {creator._count.followers} followers · {creator._count.creatorProducts}{" "}
                        picks
                      </p>
                    </div>
                  </article>
                </Link>
              ))}
            </div>
            <Link href="/discover" className="mt-8 inline-block">
              <Button variant="outline">Browse all creators</Button>
            </Link>
          </div>
        </section>
      )}

      {/* Collections */}
      <section className="border-t border-border bg-white px-6 py-20">
        <div className="mx-auto max-w-6xl">
          <p className="section-label">Shop by Collection</p>
          <h2 className="mt-3 font-display text-3xl text-ink md:text-4xl">
            Curated shelves for every craving
          </h2>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {COLLECTION_PREVIEWS.map((item) => (
              <Link key={item.title} href={item.href} className="group">
                <article className="shopmy-card overflow-hidden">
                  <div className="aspect-[3/2] overflow-hidden">
                    <img
                      src={item.image}
                      alt=""
                      className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                    />
                  </div>
                  <div className="p-6">
                    <h3 className="font-display text-xl text-ink group-hover:text-brand">
                      {item.title}
                    </h3>
                    <p className="mt-2 text-sm text-muted">{item.desc}</p>
                  </div>
                </article>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Trending products */}
      {products.length > 0 && (
        <section className="border-t border-border bg-brand-muted/40 px-6 py-20">
          <div className="mx-auto max-w-6xl">
            <p className="section-label">Trending now</p>
            <h2 className="mt-3 font-display text-3xl text-ink">What creators are recommending</h2>
            <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {products.map((product) => (
                <Link key={product.id} href={`/products/${product.id}`} className="group">
                  <article className="shopmy-card overflow-hidden">
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
                    <div className="p-4">
                      {product.brand && (
                        <p className="text-[10px] font-semibold uppercase tracking-widest text-muted">
                          {product.brand}
                        </p>
                      )}
                      <h3 className="mt-1 line-clamp-2 text-sm font-medium text-ink">
                        {product.name}
                      </h3>
                      {product.priceCents && (
                        <p className="mt-2 text-sm font-medium text-brand">
                          ${(product.priceCents / 100).toFixed(2)}
                        </p>
                      )}
                    </div>
                  </article>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* For Creators CTA */}
      <section className="bg-brand-gradient px-6 py-20 text-white">
        <div className="mx-auto max-w-4xl text-center">
          <LogoMark size={56} className="mx-auto shadow-card" />
          <p className="mt-6 text-xs font-semibold uppercase tracking-[0.2em] text-white/70">
            For creators
          </p>
          <h2 className="mt-4 font-display text-3xl md:text-4xl">
            Turn your taste into lasting revenue
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-white/80">
            Paste any grocery product URL — snacks, drinks, supplements, produce, or
            anything consumable. Build your storefront and earn when your audience shops.
          </p>
          <Link href="/signup?role=creator" className="mt-8 inline-block">
            <Button size="lg" className="bg-white text-brand hover:bg-white/90">
              Apply to be a creator
            </Button>
          </Link>
        </div>
      </section>

      <section className="border-t border-border bg-cream px-6 py-12">
        <div className="mx-auto max-w-4xl text-center">
          <p className="text-sm text-muted">
            The best things in life are worth sharing — especially what&apos;s in your cart.
          </p>
        </div>
      </section>
    </div>
  );
}
