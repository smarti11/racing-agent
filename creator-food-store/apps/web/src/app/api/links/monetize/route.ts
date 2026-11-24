import { NextRequest, NextResponse } from "next/server";
import { monetizeUrl, generateShortCode } from "@repo/affiliate-engine";
import { prisma } from "@repo/db";
import { auth } from "@/auth";

export async function POST(req: NextRequest) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { url, note, titleHint } = await req.json();
  if (!url) {
    return NextResponse.json({ error: "URL required" }, { status: 400 });
  }

  try {
    const resolved = monetizeUrl({
      url,
      creatorId: session.user.id,
      productId: "pending",
      amazonTag: process.env.AMAZON_ASSOCIATE_TAG,
      impactMediaPartnerId: process.env.IMPACT_MEDIA_PARTNER_ID,
      titleHint,
    });

    let product = await prisma.product.findFirst({
      where: {
        retailer: resolved.product.retailer,
        retailerId: resolved.product.retailerId ?? undefined,
      },
    });

    if (!product) {
      product = await prisma.product.create({
        data: {
          name: resolved.product.name,
          brand: resolved.product.brand,
          sourceUrl: resolved.product.sourceUrl,
          retailer: resolved.product.retailer,
          retailerId: resolved.product.retailerId,
          category: resolved.product.category,
          imageUrl: resolved.product.imageUrl,
          priceCents: resolved.product.priceCents,
        },
      });
    }

    const fullMonetized = monetizeUrl({
      url,
      creatorId: session.user.id,
      productId: product.id,
      amazonTag: process.env.AMAZON_ASSOCIATE_TAG,
      impactMediaPartnerId: process.env.IMPACT_MEDIA_PARTNER_ID,
      titleHint,
    });

    let shortCode = generateShortCode();
    while (await prisma.trackedLink.findUnique({ where: { shortCode } })) {
      shortCode = generateShortCode();
    }

    const appUrl = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";

    const link = await prisma.trackedLink.create({
      data: {
        shortCode,
        creatorId: session.user.id,
        productId: product.id,
        destinationUrl: fullMonetized.offer.destinationUrl,
      },
    });

    return NextResponse.json({
      product,
      trackedLink: `${appUrl}/go/${link.shortCode}`,
      commissionRate: fullMonetized.offer.commissionRate,
      note,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to monetize URL";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
