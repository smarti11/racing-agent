import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Google from "next-auth/providers/google";
import bcrypt from "bcryptjs";
import { prisma } from "@repo/db";
import type { SessionUser } from "@repo/api";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
      allowDangerousEmailAccountLinking: true,
    }),
    {
      id: "instagram",
      name: "Instagram",
      type: "oauth",
      authorization: {
        url: "https://api.instagram.com/oauth/authorize",
        params: { scope: "user_profile" },
      },
      token: "https://api.instagram.com/oauth/access_token",
      userinfo: "https://graph.instagram.com/me?fields=id,username",
      clientId: process.env.INSTAGRAM_CLIENT_ID,
      clientSecret: process.env.INSTAGRAM_CLIENT_SECRET,
      profile(profile) {
        return {
          id: profile.id,
          name: profile.username,
          email: `${profile.username}@instagram.local`,
          image: null,
        };
      },
    },
    {
      id: "tiktok",
      name: "TikTok",
      type: "oauth",
      authorization: {
        url: "https://www.tiktok.com/v2/auth/authorize/",
        params: { scope: "user.info.basic" },
      },
      token: "https://open.tiktokapis.com/v2/oauth/token/",
      userinfo: "https://open.tiktokapis.com/v2/user/info/",
      clientId: process.env.TIKTOK_CLIENT_KEY,
      clientSecret: process.env.TIKTOK_CLIENT_SECRET,
      profile(profile) {
        const user = profile.data?.user ?? profile;
        return {
          id: user.open_id ?? user.id,
          name: user.display_name ?? user.username,
          email: `${user.open_id ?? user.id}@tiktok.local`,
          image: user.avatar_url,
        };
      },
    },
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null;
        const user = await prisma.user.findUnique({
          where: { email: credentials.email as string },
        });
        if (!user?.passwordHash) return null;
        const valid = await bcrypt.compare(
          credentials.password as string,
          user.passwordHash
        );
        if (!valid) return null;
        return {
          id: user.id,
          email: user.email,
          name: user.name,
          image: user.avatarUrl,
        };
      },
    }),
  ],
  callbacks: {
    async signIn({ user, account }) {
      if (!user.email) return false;

      const existing = await prisma.user.findUnique({
        where: { email: user.email },
      });

      if (!existing && account?.provider !== "credentials") {
        const baseHandle = (user.name ?? user.email.split("@")[0])
          .toLowerCase()
          .replace(/[^a-z0-9_]/g, "")
          .slice(0, 20);
        let handle = baseHandle || "user";
        let suffix = 1;
        while (await prisma.user.findUnique({ where: { handle } })) {
          handle = `${baseHandle}${suffix++}`;
        }

        const newUser = await prisma.user.create({
          data: {
            email: user.email,
            name: user.name,
            handle,
            avatarUrl: user.image,
            role: "CONSUMER",
          },
        });

        if (account) {
          await prisma.account.create({
            data: {
              userId: newUser.id,
              type: account.type,
              provider: account.provider,
              providerAccountId: account.providerAccountId,
              access_token: account.access_token,
              refresh_token: account.refresh_token,
              expires_at: account.expires_at,
              token_type: account.token_type,
              scope: account.scope,
              id_token: account.id_token,
            },
          });
        }
      } else if (existing && account) {
        await prisma.account.upsert({
          where: {
            provider_providerAccountId: {
              provider: account.provider,
              providerAccountId: account.providerAccountId,
            },
          },
          update: {
            access_token: account.access_token,
            refresh_token: account.refresh_token,
          },
          create: {
            userId: existing.id,
            type: account.type,
            provider: account.provider,
            providerAccountId: account.providerAccountId,
            access_token: account.access_token,
            refresh_token: account.refresh_token,
            expires_at: account.expires_at,
          },
        });

        if (account.provider === "instagram" && user.name) {
          await prisma.user.update({
            where: { id: existing.id },
            data: { instagramUrl: `https://instagram.com/${user.name}` },
          });
        }
        if (account.provider === "tiktok" && user.name) {
          await prisma.user.update({
            where: { id: existing.id },
            data: { tiktokUrl: `https://tiktok.com/@${user.name}` },
          });
        }
      }

      return true;
    },
    async session({ session, token }) {
      if (token.sub) {
        const dbUser = await prisma.user.findUnique({
          where: { id: token.sub },
          select: {
            id: true,
            email: true,
            name: true,
            handle: true,
            role: true,
            avatarUrl: true,
          },
        });
        if (dbUser) {
          session.user = {
            ...session.user,
            id: dbUser.id,
            handle: dbUser.handle,
            role: dbUser.role,
          } as SessionUser & typeof session.user;
        }
      }
      return session;
    },
    async jwt({ token, user }) {
      if (user) token.sub = user.id;
      return token;
    },
  },
  pages: {
    signIn: "/login",
  },
  session: { strategy: "jwt" },
  secret: process.env.AUTH_SECRET,
});
