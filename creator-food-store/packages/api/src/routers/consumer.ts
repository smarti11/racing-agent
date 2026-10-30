import { z } from "zod";
import { prisma } from "@repo/db";
import { router, protectedProcedure, publicProcedure } from "../trpc";
import { TRPCError } from "@trpc/server";

export const consumerRouter = router({
  follow: protectedProcedure
    .input(z.object({ creatorId: z.string() }))
    .mutation(async ({ ctx, input }) => {
      if (ctx.user.id === input.creatorId) {
        throw new TRPCError({ code: "BAD_REQUEST", message: "Cannot follow yourself" });
      }
      await prisma.follow.upsert({
        where: {
          followerId_followingId: {
            followerId: ctx.user.id,
            followingId: input.creatorId,
          },
        },
        update: {},
        create: { followerId: ctx.user.id, followingId: input.creatorId },
      });
      await prisma.creatorProfile.updateMany({
        where: { userId: input.creatorId },
        data: { followerCount: { increment: 1 } },
      });
      return { success: true };
    }),

  unfollow: protectedProcedure
    .input(z.object({ creatorId: z.string() }))
    .mutation(async ({ ctx, input }) => {
      const deleted = await prisma.follow.deleteMany({
        where: { followerId: ctx.user.id, followingId: input.creatorId },
      });
      if (deleted.count > 0) {
        await prisma.creatorProfile.updateMany({
          where: { userId: input.creatorId },
          data: { followerCount: { decrement: 1 } },
        });
      }
      return { success: true };
    }),

  isFollowing: protectedProcedure
    .input(z.object({ creatorId: z.string() }))
    .query(async ({ ctx, input }) => {
      const follow = await prisma.follow.findUnique({
        where: {
          followerId_followingId: {
            followerId: ctx.user.id,
            followingId: input.creatorId,
          },
        },
      });
      return !!follow;
    }),

  feed: protectedProcedure
    .input(z.object({ limit: z.number().min(1).max(50).default(20) }))
    .query(async ({ ctx, input }) => {
      const following = await prisma.follow.findMany({
        where: { followerId: ctx.user.id },
        select: { followingId: true },
      });
      const creatorIds = following.map((f) => f.followingId);
      if (creatorIds.length === 0) return [];

      return prisma.creatorProduct.findMany({
        where: { creatorId: { in: creatorIds } },
        take: input.limit,
        orderBy: { createdAt: "desc" },
        include: {
          product: true,
          creator: { select: { id: true, name: true, handle: true, avatarUrl: true } },
        },
      });
    }),

  saveProduct: protectedProcedure
    .input(
      z.object({
        productId: z.string(),
        collectionId: z.string().optional(),
      })
    )
    .mutation(async ({ ctx, input }) => {
      return prisma.savedProduct.upsert({
        where: {
          userId_productId: { userId: ctx.user.id, productId: input.productId },
        },
        update: { collectionId: input.collectionId },
        create: {
          userId: ctx.user.id,
          productId: input.productId,
          collectionId: input.collectionId,
        },
        include: { product: true },
      });
    }),

  unsaveProduct: protectedProcedure
    .input(z.object({ productId: z.string() }))
    .mutation(async ({ ctx, input }) => {
      await prisma.savedProduct.deleteMany({
        where: { userId: ctx.user.id, productId: input.productId },
      });
      return { success: true };
    }),

  locker: protectedProcedure.query(async ({ ctx }) => {
    return prisma.savedProduct.findMany({
      where: { userId: ctx.user.id },
      orderBy: { createdAt: "desc" },
      include: { product: { include: { affiliateOffers: { take: 1 } } } },
    });
  }),

  markPurchased: protectedProcedure
    .input(
      z.object({
        productId: z.string(),
        isPurchased: z.boolean(),
        isGifted: z.boolean().optional(),
      })
    )
    .mutation(async ({ ctx, input }) => {
      return prisma.savedProduct.update({
        where: {
          userId_productId: { userId: ctx.user.id, productId: input.productId },
        },
        data: {
          isPurchased: input.isPurchased,
          ...(input.isGifted !== undefined ? { isGifted: input.isGifted } : {}),
        },
      });
    }),

  createPriceAlert: protectedProcedure
    .input(
      z.object({
        productId: z.string(),
        targetPriceCents: z.number().min(1),
      })
    )
    .mutation(async ({ ctx, input }) => {
      return prisma.priceAlert.create({
        data: {
          userId: ctx.user.id,
          productId: input.productId,
          targetPriceCents: input.targetPriceCents,
        },
      });
    }),

  priceAlerts: protectedProcedure.query(async ({ ctx }) => {
    return prisma.priceAlert.findMany({
      where: { userId: ctx.user.id, status: "ACTIVE" },
      include: { product: true },
      orderBy: { createdAt: "desc" },
    });
  }),

  cancelPriceAlert: protectedProcedure
    .input(z.object({ alertId: z.string() }))
    .mutation(async ({ ctx, input }) => {
      await prisma.priceAlert.updateMany({
        where: { id: input.alertId, userId: ctx.user.id },
        data: { status: "CANCELLED" },
      });
      return { success: true };
    }),
});
