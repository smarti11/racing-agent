import { z } from "zod";
import { prisma } from "@repo/db";
import { router, creatorProcedure } from "../trpc";

export const analyticsRouter = router({
  dashboard: creatorProcedure
    .input(
      z
        .object({
          days: z.number().min(1).max(90).default(30),
        })
        .optional()
    )
    .query(async ({ ctx, input }) => {
      const days = input?.days ?? 30;
      const since = new Date();
      since.setDate(since.getDate() - days);

      const [
        totalClicks,
        totalConversions,
        confirmedConversions,
        earnings,
        clicksByDay,
        topProducts,
        recentConversions,
        payouts,
      ] = await Promise.all([
        prisma.click.count({
          where: {
            link: { creatorId: ctx.user.id },
            createdAt: { gte: since },
          },
        }),
        prisma.conversion.count({
          where: { creatorId: ctx.user.id, createdAt: { gte: since } },
        }),
        prisma.conversion.aggregate({
          where: {
            creatorId: ctx.user.id,
            status: "CONFIRMED",
            createdAt: { gte: since },
          },
          _sum: { commission: true, orderAmount: true },
          _count: true,
        }),
        prisma.creatorProfile.findUnique({
          where: { userId: ctx.user.id },
          select: { totalEarnings: true, pendingEarnings: true, stripeOnboarded: true },
        }),
        prisma.click.findMany({
          where: {
            link: { creatorId: ctx.user.id },
            createdAt: { gte: since },
          },
          select: { createdAt: true },
        }),
        prisma.conversion.groupBy({
          by: ["productId"],
          where: { creatorId: ctx.user.id, createdAt: { gte: since } },
          _sum: { commission: true },
          _count: true,
          orderBy: { _sum: { commission: "desc" } },
          take: 10,
        }),
        prisma.conversion.findMany({
          where: { creatorId: ctx.user.id },
          take: 10,
          orderBy: { createdAt: "desc" },
          include: { product: { select: { name: true, imageUrl: true } } },
        }),
        prisma.earning.findMany({
          where: { creatorId: ctx.user.id },
          orderBy: { createdAt: "desc" },
          take: 10,
        }),
      ]);

      const productIds = topProducts.map((p) => p.productId);
      const products = await prisma.product.findMany({
        where: { id: { in: productIds } },
        select: { id: true, name: true, retailer: true, imageUrl: true },
      });
      const productMap = Object.fromEntries(products.map((p) => [p.id, p]));

      const clicksPerDay: Record<string, number> = {};
      for (const click of clicksByDay) {
        const day = click.createdAt.toISOString().slice(0, 10);
        clicksPerDay[day] = (clicksPerDay[day] ?? 0) + 1;
      }

      const conversionRate =
        totalClicks > 0 ? (totalConversions / totalClicks) * 100 : 0;

      return {
        totalClicks,
        totalConversions,
        conversionRate,
        confirmedCommission: confirmedConversions._sum.commission ?? 0,
        confirmedGmv: confirmedConversions._sum.orderAmount ?? 0,
        confirmedCount: confirmedConversions._count,
        totalEarnings: earnings?.totalEarnings ?? 0,
        pendingEarnings: earnings?.pendingEarnings ?? 0,
        stripeOnboarded: earnings?.stripeOnboarded ?? false,
        clicksPerDay,
        topProducts: topProducts.map((tp) => ({
          product: productMap[tp.productId],
          commission: tp._sum.commission ?? 0,
          conversions: tp._count,
        })),
        recentConversions,
        payouts,
      };
    }),
});
