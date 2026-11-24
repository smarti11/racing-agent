import { z } from "zod";
import { prisma } from "@repo/db";
import {
  monetizeUrl,
  generateShortCode,
  resolveProductFromUrl,
} from "@repo/affiliate-engine";
import { router, creatorProcedure, publicProcedure } from "../trpc";
import { TRPCError } from "@trpc/server";

export const storefrontRouter = router({
  getPublic: publicProcedure
    .input(z.object({ handle: z.string() }))
    .query(async ({ input }) => {
      const creator = await prisma.user.findUnique({
        where: { handle: input.handle },
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
                },
              },
            },
          },
          _count: { select: { followers: true } },
        },
      });
      if (!creator || creator.role !== "CREATOR") {
        throw new TRPCError({ code: "NOT_FOUND", message: "Creator not found" });
      }
      return creator;
    }),

  addProduct: creatorProcedure
    .input(
      z.object({
        url: z.string().url(),
        note: z.string().max(500).optional(),
        collectionId: z.string().optional(),
        titleHint: z.string().optional(),
      })
    )
    .mutation(async ({ ctx, input }) => {
      const resolved = resolveProductFromUrl(input.url, input.titleHint);

      let product = await prisma.product.findFirst({
        where: {
          retailer: resolved.retailer,
          retailerId: resolved.retailerId ?? undefined,
        },
      });

      if (!product) {
        product = await prisma.product.create({
          data: {
            name: resolved.name,
            brand: resolved.brand,
            sourceUrl: resolved.sourceUrl,
            retailer: resolved.retailer,
            retailerId: resolved.retailerId,
            category: resolved.category,
            imageUrl: resolved.imageUrl,
            priceCents: resolved.priceCents,
          },
        });
      }

      const monetized = monetizeUrl({
        url: input.url,
        creatorId: ctx.user.id,
        productId: product.id,
        amazonTag: process.env.AMAZON_ASSOCIATE_TAG,
        impactMediaPartnerId: process.env.IMPACT_MEDIA_PARTNER_ID,
        titleHint: input.titleHint,
      });

      const offer = await prisma.affiliateOffer.upsert({
        where: {
          id: `offer-${product.id}-${monetized.offer.network}`,
        },
        update: {
          commissionRate: monetized.offer.commissionRate,
          affiliateUrlTemplate: monetized.offer.destinationUrl,
        },
        create: {
          id: `offer-${product.id}-${monetized.offer.network}`,
          productId: product.id,
          network: monetized.offer.network,
          commissionRate: monetized.offer.commissionRate,
          affiliateUrlTemplate: monetized.offer.destinationUrl,
          networkProductId: monetized.offer.networkProductId,
        },
      });

      let shortCode = generateShortCode();
      while (await prisma.trackedLink.findUnique({ where: { shortCode } })) {
        shortCode = generateShortCode();
      }

      await prisma.trackedLink.create({
        data: {
          shortCode,
          creatorId: ctx.user.id,
          productId: product.id,
          offerId: offer.id,
          destinationUrl: monetized.offer.destinationUrl,
        },
      });

      const maxOrder = await prisma.creatorProduct.aggregate({
        where: { creatorId: ctx.user.id },
        _max: { sortOrder: true },
      });

      const creatorProduct = await prisma.creatorProduct.upsert({
        where: {
          creatorId_productId: { creatorId: ctx.user.id, productId: product.id },
        },
        update: { note: input.note, collectionId: input.collectionId },
        create: {
          creatorId: ctx.user.id,
          productId: product.id,
          collectionId: input.collectionId,
          note: input.note,
          sortOrder: (maxOrder._max.sortOrder ?? -1) + 1,
        },
        include: { product: true },
      });

      const appUrl = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
      return {
        creatorProduct,
        trackedLink: `${appUrl}/go/${shortCode}`,
        commissionRate: monetized.offer.commissionRate,
      };
    }),

  reorderProducts: creatorProcedure
    .input(
      z.object({
        items: z.array(
          z.object({ id: z.string(), sortOrder: z.number(), collectionId: z.string().nullable().optional() })
        ),
      })
    )
    .mutation(async ({ ctx, input }) => {
      await Promise.all(
        input.items.map((item) =>
          prisma.creatorProduct.updateMany({
            where: { id: item.id, creatorId: ctx.user.id },
            data: {
              sortOrder: item.sortOrder,
              ...(item.collectionId !== undefined
                ? { collectionId: item.collectionId }
                : {}),
            },
          })
        )
      );
      return { success: true };
    }),

  removeProduct: creatorProcedure
    .input(z.object({ creatorProductId: z.string() }))
    .mutation(async ({ ctx, input }) => {
      await prisma.creatorProduct.deleteMany({
        where: { id: input.creatorProductId, creatorId: ctx.user.id },
      });
      return { success: true };
    }),
});
