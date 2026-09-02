import { prisma } from "@repo/db";
import { notFound } from "next/navigation";
import Link from "next/link";
import { Badge } from "@repo/ui";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function ProductPage({ params }: Props) {
  const { id } = await params;
  const product = await prisma.product.findUnique({
    where: { id },
    include: {
      affiliateOffers: { where: { isActive: true } },
      creatorProducts: {
        include: {
          creator: { select: { name: true, handle: true, avatarUrl: true } },
        },
      },
      priceHistory: { orderBy: { recordedAt: "desc" }, take: 10 },
    },
  });

  if (!product) notFound();

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="grid gap-8 md:grid-cols-2">
        <div className="aspect-square rounded-xl bg-stone-100 flex items-center justify-center text-6xl">
          {product.imageUrl ? (
            <img
              src={product.imageUrl}
              alt={product.name}
              className="h-full w-full rounded-xl object-cover"
            />
          ) : (
            "🍽️"
          )}
        </div>
        <div>
          <Badge variant="info">{product.category.replace("_", " ")}</Badge>
          <h1 className="mt-2 text-3xl font-bold">{product.name}</h1>
          {product.brand && (
            <p className="text-lg text-stone-500">{product.brand}</p>
          )}
          {product.priceCents && (
            <p className="mt-4 text-2xl font-bold">
              ${(product.priceCents / 100).toFixed(2)}
            </p>
          )}
          {product.affiliateOffers[0] && (
            <p className="text-sm text-muted">
              {(product.affiliateOffers[0].commissionRate * 100).toFixed(0)}%
              creator commission
            </p>
          )}
          <a
            href={product.sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-6 inline-block bg-ink px-6 py-3 text-sm uppercase tracking-wider text-white hover:bg-ink/90"
          >
            View at {product.retailer}
          </a>
        </div>
      </div>

      {product.creatorProducts.length > 0 && (
        <section className="mt-12">
          <h2 className="text-xl font-semibold">Recommended by</h2>
          <div className="mt-4 space-y-3">
            {product.creatorProducts.map((cp) => (
              <Link
                key={cp.id}
                href={`/@${cp.creator.handle}`}
                className="flex items-center gap-3 rounded-lg border p-3 hover:bg-stone-50"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-cream font-display text-ink">
                  👨‍🍳
                </div>
                <div>
                  <p className="font-medium">{cp.creator.name}</p>
                  <p className="text-sm text-stone-500">@{cp.creator.handle}</p>
                  {cp.note && (
                    <p className="text-sm italic">&ldquo;{cp.note}&rdquo;</p>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
