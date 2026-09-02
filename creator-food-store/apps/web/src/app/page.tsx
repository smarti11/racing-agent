import Link from "next/link";
import { Button } from "@repo/ui";

export default function HomePage() {
  return (
    <div>
      <section className="bg-gradient-to-b from-emerald-50 to-stone-50 px-4 py-20">
        <div className="mx-auto max-w-4xl text-center">
          <h1 className="text-4xl font-bold tracking-tight text-stone-900 sm:text-5xl">
            Your taste. Your storefront.
            <span className="block text-emerald-600">Earn from every bite.</span>
          </h1>
          <p className="mt-6 text-lg text-stone-600">
            PantryLink lets food creators build personalized storefronts of products
            they love. When followers buy through your links, you earn commission.
          </p>
          <div className="mt-8 flex justify-center gap-4">
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

      <section className="mx-auto max-w-6xl px-4 py-16">
        <h2 className="text-center text-2xl font-bold">How it works</h2>
        <div className="mt-12 grid gap-8 md:grid-cols-3">
          {[
            {
              step: "1",
              title: "Curate your picks",
              desc: "Paste any food product URL from Amazon, Walmart, Instacart, and more.",
            },
            {
              step: "2",
              title: "Share your storefront",
              desc: "Your personalized @handle page showcases everything you recommend.",
            },
            {
              step: "3",
              title: "Earn commission",
              desc: "When followers buy through your links, you get paid weekly via Stripe.",
            },
          ].map((item) => (
            <div key={item.step} className="rounded-xl border bg-white p-6 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-xl font-bold text-emerald-700">
                {item.step}
              </div>
              <h3 className="mt-4 font-semibold">{item.title}</h3>
              <p className="mt-2 text-sm text-stone-600">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-t bg-white px-4 py-12">
        <div className="mx-auto max-w-4xl text-center">
          <p className="text-sm text-stone-500">
            PantryLink is a food-only creator commerce platform. We support affiliate
            tracking through Amazon Associates, Impact, and direct brand partnerships.
          </p>
        </div>
      </section>
    </div>
  );
}
