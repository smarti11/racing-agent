import { Stack, Tabs } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { httpBatchLink } from "@trpc/client";
import { createTRPCReact } from "@trpc/react-query";
import type { AppRouter } from "@repo/api";
import superjson from "superjson";
import Constants from "expo-constants";

export const trpc = createTRPCReact<AppRouter>();

const queryClient = new QueryClient();
const apiUrl = Constants.expoConfig?.extra?.apiUrl ?? "http://localhost:3000";

const trpcClient = trpc.createClient({
  links: [
    httpBatchLink({
      url: `${apiUrl}/api/trpc`,
      transformer: superjson,
    }),
  ],
});

export default function RootLayout() {
  return (
    <trpc.Provider client={trpcClient} queryClient={queryClient}>
      <QueryClientProvider client={queryClient}>
        <StatusBar style="auto" />
        <Tabs
          screenOptions={{
            tabBarActiveTintColor: "#0a0a0a",
            headerStyle: { backgroundColor: "#0a0a0a" },
            headerTintColor: "#fff",
          }}
        >
          <Tabs.Screen name="index" options={{ title: "Discover" }} />
          <Tabs.Screen name="locker" options={{ title: "My Locker" }} />
          <Tabs.Screen name="profile" options={{ title: "Profile" }} />
          <Tabs.Screen name="earnings" options={{ title: "Earnings" }} />
        </Tabs>
      </QueryClientProvider>
    </trpc.Provider>
  );
}
