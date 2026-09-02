import { prisma } from "@repo/db";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { StorefrontView } from "@/components/storefront-view";

interface Props {
  params: Promise<{ handle: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { handle } = await params;
  const creator = await prisma.user.findUnique({
    where: { handle },
    select: { name: true, bio: true },
  });
  if (!creator) return { title: "Creator not found" };
  return {
    title: `${creator.name} (@${handle}) | PantryLink`,
    description: creator.bio ?? `Food recommendations by ${creator.name}`,
    openGraph: {
      title: `${creator.name}'s Food Picks`,
      description: creator.bio ?? undefined,
    },
  };
}

export default async function StorefrontPage({ params }: Props) {
  const { handle } = await params;

  const creator = await prisma.user.findUnique({
    where: { handle },
    include: {
      creatorProfile: true,
      collections: {
        where: { visibility: "PUBLIC" },
        orderBy: { sortOrder: "asc" },
        include: {
          creatorProducts: {
            orderBy: [{ isPinned: "desc" }, { sortOrder: "asc" }],
            include: {
              product: {
                include: {
                  affiliateOffers: { where: { isActive: true }, take: 1 },
                },
              },
            },
          },
        },
      },
      creatorProducts: {
        where: { collectionId: null },
        orderBy: [{ isPinned: "desc" }, { sortOrder: "asc" }],
        include: {
          product: {
            include: {
              affiliateOffers: { where: { isActive: true }, take: 1 },
              trackedLinks: { take: 1, orderBy: { createdAt: "desc" } },
            },
          },
        },
      },
      _count: { select: { followers: true } },
    },
  });

  if (!creator || creator.role !== "CREATOR") notFound();

  const links = await prisma.trackedLink.findMany({
    where: { creatorId: creator.id },
    select: { productId: true, shortCode: true },
  });
  const linkMap = Object.fromEntries(links.map((l) => [l.productId, l.shortCode]));

  return <StorefrontView creator={creator} linkMap={linkMap} />;
}
