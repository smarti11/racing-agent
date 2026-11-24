import { z } from "zod";
import { prisma } from "@repo/db";
import { router, adminProcedure, creatorProcedure } from "../trpc";

export const adminRouter = router({
  moderationQueue: adminProcedure.query(async () => {
    return prisma.moderationItem.findMany({
      where: { status: "pending" },
      orderBy: { createdAt: "desc" },
      take: 50,
    });
  }),

  approveProduct: adminProcedure
    .input(z.object({ productId: z.string() }))
    .mutation(async ({ ctx, input }) => {
      await prisma.product.update({
        where: { id: input.productId },
        data: { isApproved: true },
      });
      await prisma.moderationItem.updateMany({
        where: { productId: input.productId, status: "pending" },
        data: { status: "approved", moderatorId: ctx.user.id, resolvedAt: new Date() },
      });
      return { success: true };
    }),

  rejectProduct: adminProcedure
    .input(z.object({ productId: z.string(), reason: z.string() }))
    .mutation(async ({ ctx, input }) => {
      await prisma.product.update({
        where: { id: input.productId },
        data: { isApproved: false },
      });
      await prisma.moderationItem.create({
        data: {
          productId: input.productId,
          reason: input.reason,
          status: "rejected",
          moderatorId: ctx.user.id,
          resolvedAt: new Date(),
        },
      });
      return { success: true };
    }),

  stats: adminProcedure.query(async () => {
    const [users, creators, products, conversions, gmv] = await Promise.all([
      prisma.user.count(),
      prisma.user.count({ where: { role: "CREATOR" } }),
      prisma.product.count(),
      prisma.conversion.count({ where: { status: "CONFIRMED" } }),
      prisma.conversion.aggregate({
        where: { status: "CONFIRMED" },
        _sum: { orderAmount: true, commission: true },
      }),
    ]);
    return {
      users,
      creators,
      products,
      conversions,
      gmv: gmv._sum.orderAmount ?? 0,
      totalCommission: gmv._sum.commission ?? 0,
    };
  }),
});

export const stripeRouter = router({
  getOnboardingStatus: creatorProcedure.query(async ({ ctx }) => {
    const profile = await prisma.creatorProfile.findUnique({
      where: { userId: ctx.user.id },
    });
    return {
      stripeConnectId: profile?.stripeConnectId ?? null,
      stripeOnboarded: profile?.stripeOnboarded ?? false,
    };
  }),
});
