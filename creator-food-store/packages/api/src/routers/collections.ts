import { z } from "zod";
import { prisma } from "@repo/db";
import { router, protectedProcedure, publicProcedure } from "../trpc";
import { TRPCError } from "@trpc/server";

export const collectionsRouter = router({
  list: protectedProcedure.query(async ({ ctx }) => {
    return prisma.collection.findMany({
      where: { userId: ctx.user.id },
      orderBy: { sortOrder: "asc" },
      include: { _count: { select: { creatorProducts: true } } },
    });
  }),

  create: protectedProcedure
    .input(
      z.object({
        name: z.string().min(1).max(100),
        description: z.string().max(500).optional(),
        visibility: z.enum(["PUBLIC", "PRIVATE", "COLLABORATIVE"]).default("PUBLIC"),
      })
    )
    .mutation(async ({ ctx, input }) => {
      const maxOrder = await prisma.collection.aggregate({
        where: { userId: ctx.user.id },
        _max: { sortOrder: true },
      });
      return prisma.collection.create({
        data: {
          userId: ctx.user.id,
          name: input.name,
          description: input.description,
          visibility: input.visibility,
          sortOrder: (maxOrder._max.sortOrder ?? -1) + 1,
        },
      });
    }),

  update: protectedProcedure
    .input(
      z.object({
        id: z.string(),
        name: z.string().min(1).max(100).optional(),
        description: z.string().max(500).optional(),
        visibility: z.enum(["PUBLIC", "PRIVATE", "COLLABORATIVE"]).optional(),
      })
    )
    .mutation(async ({ ctx, input }) => {
      const { id, ...data } = input;
      const result = await prisma.collection.updateMany({
        where: { id, userId: ctx.user.id },
        data,
      });
      if (result.count === 0) throw new TRPCError({ code: "NOT_FOUND" });
      return prisma.collection.findUnique({ where: { id } });
    }),

  delete: protectedProcedure
    .input(z.object({ id: z.string() }))
    .mutation(async ({ ctx, input }) => {
      await prisma.creatorProduct.updateMany({
        where: { collectionId: input.id, creatorId: ctx.user.id },
        data: { collectionId: null },
      });
      await prisma.collection.deleteMany({
        where: { id: input.id, userId: ctx.user.id },
      });
      return { success: true };
    }),
});
