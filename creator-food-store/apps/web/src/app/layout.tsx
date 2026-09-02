import type { Metadata } from "next";
import { Navbar } from "@/components/navbar";
import { AuthProvider } from "@/components/auth-provider";
import { TRPCProvider } from "@/lib/trpc";
import "./globals.css";

export const metadata: Metadata = {
  title: "PantryLink — Food Creator Storefronts",
  description:
    "Build your personalized food storefront. Earn commission when followers shop your recommendations.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <TRPCProvider>
            <Navbar />
            <main>{children}</main>
          </TRPCProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
