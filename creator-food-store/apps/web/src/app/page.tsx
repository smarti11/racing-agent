import Link from "next/link";
import { Button } from "@repo/ui";

export default function HomePage() {
  return (
    <div>
      {/* Hero — ShopMy-style editorial */}
      <section className="bg-white px-6 py-24 md:py-32">
        <div className="mx-auto max-w-4xl text-center">
          <p className="section-label">Curated for food lovers, not the algorithm</p>
          <h1 className="mt-6 font-display text-4xl leading-tight text-ink md:text-6xl md:leading-[1.1]">
            Shop the recommendations of the world&apos;s most trusted food curators
          </h1>
          <p className="mx-auto mt-8 max-w-2xl text-lg text-muted">
            GoodCart lets creators build personalized food storefronts. When followers
            buy through your links, you earn commission — just like the tastemakers you
            already follow.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link href="/signup?role=creator">
              <Button size="lg">Start your storefront</Button>
            </Link>
            <Link href="/discover">
              <Button variant="outline" size="lg">
                Explore creators
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Shop by Creator */}
      <section className="border-t border-border bg-cream px-6 py-20">
        <div className="mx-auto max-w-6xl">
          <p className="section-label">Shop by Creator</p>
          <h2 className="mt-3 font-display text-3xl text-ink md:text-4xl">
            Insider access to your favorite food tastemakers&apos; most loved products
          </h2>
          <p className="mt-4 max-w-2xl text-muted">
            Follow creators who share your taste — from pantry staples and snacks to
            meal kits and specialty ingredients. Every pick is personal, not algorithmic.
          </p>
          <Link href="/discover" className="mt-8 inline-block">
            <Button variant="outline">Browse creators</Button>
          </Link>
        </div>
      </section>

      {/* Shop by Collection */}
      <section className="border-t border-border bg-white px-6 py-20">
        <div className="mx-auto max-w-6xl">
          <p className="section-label">Shop by Collection</p>
          <h2 className="mt-3 font-display text-3xl text-ink md:text-4xl">
            Curated shelves for every craving
          </h2>
          <p className="mt-4 max-w-2xl text-muted">
            Morning routines, pantry staples, date-night ingredients — creators organize
            their picks into collections so you can shop exactly what you need.
          </p>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {[
              { title: "Morning Routine", desc: "Coffee, oats, and everything in between" },
              { title: "Pantry Staples", desc: "The ingredients you reach for every week" },
              { title: "Treat Yourself", desc: "Snacks and specialty finds worth sharing" },
            ].map((item) => (
              <div key={item.title} className="shopmy-card p-8">
                <h3 className="font-display text-xl text-ink">{item.title}</h3>
                <p className="mt-2 text-sm text-muted">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* For Creators CTA */}
      <section className="border-t border-border bg-ink px-6 py-20 text-white">
        <div className="mx-auto max-w-4xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-white/60">
            For creators
          </p>
          <h2 className="mt-4 font-display text-3xl md:text-4xl">
            Turn your taste into lasting revenue
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-white/70">
            Paste any food product URL, build your storefront in minutes, and earn
            commission when your audience shops your recommendations.
          </p>
          <Link href="/signup?role=creator" className="mt-8 inline-block">
            <Button
              size="lg"
              className="bg-white text-ink hover:bg-white/90"
            >
              Apply to be a creator
            </Button>
          </Link>
        </div>
      </section>

      {/* Mobile note — ShopMy pattern */}
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
