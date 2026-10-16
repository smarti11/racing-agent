import { router } from "./trpc";
import { authRouter, profileRouter } from "./routers/auth";
import { storefrontRouter } from "./routers/storefront";
import { collectionsRouter } from "./routers/collections";
import { catalogRouter } from "./routers/catalog";
import { consumerRouter } from "./routers/consumer";
import { analyticsRouter } from "./routers/analytics";
import { adminRouter, stripeRouter } from "./routers/admin";

export const appRouter = router({
  auth: authRouter,
  profile: profileRouter,
  storefront: storefrontRouter,
  collections: collectionsRouter,
  catalog: catalogRouter,
  consumer: consumerRouter,
  analytics: analyticsRouter,
  admin: adminRouter,
  stripe: stripeRouter,
});

export type AppRouter = typeof appRouter;

export { type Context, type SessionUser } from "./trpc";
