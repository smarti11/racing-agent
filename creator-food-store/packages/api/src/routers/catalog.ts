import { z } from "zod";
import { prisma } from "@repo/db";
import { router, publicProcedure, protectedProcedure } from "../trpc";

export const catalogRouter = router({
  search: publicProcedure
    .input(
      z.object({
        query: z.string().optional(),
        category: z
          .enum([
            "SNACKS",
            "BEVERAGES",
            "PANTRY",
            "MEAL_KITS",
            "SUPPLEMENTS",
            "SPECIALTY",
            "KITCHEN_TOOLS",
          ])
          .optional(),
        limit: z.number().min(1).max(50).default(20),
        offset: z.number().min(0).default(0),
      })
    )
    .query(async ({ input }) => {
      const where = {
        isApproved: true,
        ...(input.category ? { category: input.category } : {}),
        ...(input.query
          ? {
              OR: [
                { name: { contains: input.query } },
                { brand: { contains: input.query } },
              ],
            }
          : {}),
      };

      const [products, total] = await Promise.all([
        prisma.product.findMany({
          where,
          take: input.limit,
          skip: input.offset,
          orderBy: { createdAt: "desc" },
          include: {
            affiliateOffers: { where: { isActive: true }, take: 1 },
            _count: { select: { creatorProducts: true } },
          },
        }),
        prisma.product.count({ where }),
      ]);

      return { products, total };
    }),

  getById: publicProcedure
    .input(z.object({ id: z.string() }))
    .query(async ({ input }) => {
      return prisma.product.findUnique({
        where: { id: input.id },
        include: {
          affiliateOffers: { where: { isActive: true } },
          creatorProducts: {
            take: 10,
            include: {
              creator: {
                select: { id: true, name: true, handle: true, avatarUrl: true },
              },
            },
          },
          priceHistory: { orderBy: { recordedAt: "desc" }, take: 30 },
        },
      });
    }),

  discover: publicProcedure
    .input(z.object({ limit: z.number().min(1).max(20).default(10) }))
    .query(async ({ input }) => {
      const [trendingProducts, featuredCreators] = await Promise.all([
        prisma.product.findMany({
          where: { isApproved: true },
          take: input.limit,
          orderBy: { creatorProducts: { _count: "desc" } },
          include: {
            affiliateOffers: { where: { isActive: true }, take: 1 },
            _count: { select: { creatorProducts: true, savedProducts: true } },
          },
        }),
        prisma.user.findMany({
          where: { role: "CREATOR" },
          take: input.limit,
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
      ]);

      return { trendingProducts, featuredCreators };
    }),
});
