import { auth } from "@/auth";
import { appRouter } from "@repo/api";
import { fetchRequestHandler } from "@trpc/server/adapters/fetch";

const handler = (req: Request) =>
  fetchRequestHandler({
    endpoint: "/api/trpc",
    req,
    router: appRouter,
    createContext: async () => {
      const session = await auth();
      const user = session?.user as {
        id: string;
        email: string;
        name?: string | null;
        handle: string;
        role: string;
        avatarUrl?: string | null;
      } | undefined;

      return {
        user: user
          ? {
              id: user.id,
              email: user.email,
              name: user.name ?? null,
              handle: user.handle,
              role: user.role as "CREATOR" | "CONSUMER" | "ADMIN",
              avatarUrl: user.avatarUrl ?? null,
            }
          : null,
      };
    },
  });

export { handler as GET, handler as POST };
