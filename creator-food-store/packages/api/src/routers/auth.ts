import { z } from "zod";
import bcrypt from "bcryptjs";
import { prisma } from "@repo/db";
import { router, publicProcedure, protectedProcedure } from "../trpc";
import { TRPCError } from "@trpc/server";

export const authRouter = router({
  register: publicProcedure
    .input(
      z.object({
        email: z.string().email(),
        password: z.string().min(8),
        name: z.string().min(1),
        handle: z
          .string()
          .min(3)
          .max(30)
          .regex(/^[a-z0-9_]+$/),
        role: z.enum(["CREATOR", "CONSUMER"]).default("CONSUMER"),
      })
    )
    .mutation(async ({ input }) => {
      const existing = await prisma.user.findFirst({
        where: { OR: [{ email: input.email }, { handle: input.handle }] },
      });
      if (existing) {
        throw new TRPCError({
          code: "CONFLICT",
          message: "Email or handle already taken",
        });
      }

      const passwordHash = await bcrypt.hash(input.password, 12);
      const user = await prisma.user.create({
        data: {
          email: input.email,
          passwordHash,
          name: input.name,
          handle: input.handle,
          role: input.role,
          ...(input.role === "CREATOR"
            ? { creatorProfile: { create: { applicationStatus: "APPROVED" } } }
            : {}),
        },
        select: {
          id: true,
          email: true,
          name: true,
          handle: true,
          role: true,
          avatarUrl: true,
        },
      });
      return user;
    }),

  getSession: publicProcedure.query(async ({ ctx }) => ctx.user),
});

export const profileRouter = router({
  getByHandle: publicProcedure
    .input(z.object({ handle: z.string() }))
    .query(async ({ input }) => {
      const user = await prisma.user.findUnique({
        where: { handle: input.handle },
        include: {
          creatorProfile: true,
          _count: { select: { followers: true, creatorProducts: true } },
        },
      });
      if (!user) throw new TRPCError({ code: "NOT_FOUND" });
      return user;
    }),

  update: protectedProcedure
    .input(
      z.object({
        name: z.string().min(1).optional(),
        bio: z.string().max(500).optional(),
        avatarUrl: z.string().url().optional(),
        instagramUrl: z.string().url().optional().nullable(),
        tiktokUrl: z.string().url().optional().nullable(),
      })
    )
    .mutation(async ({ ctx, input }) => {
      return prisma.user.update({
        where: { id: ctx.user.id },
        data: input,
        select: {
          id: true,
          name: true,
          handle: true,
          bio: true,
          avatarUrl: true,
          instagramUrl: true,
          tiktokUrl: true,
          role: true,
        },
      });
    }),

  becomeCreator: protectedProcedure.mutation(async ({ ctx }) => {
    if (ctx.user.role === "CREATOR") return ctx.user;
    await prisma.user.update({
      where: { id: ctx.user.id },
      data: { role: "CREATOR" },
    });
    await prisma.creatorProfile.upsert({
      where: { userId: ctx.user.id },
      update: {},
      create: { userId: ctx.user.id, applicationStatus: "APPROVED" },
    });
    return { success: true };
  }),
});
