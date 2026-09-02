import type { Metadata } from "next";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { AuthProvider } from "@/components/auth-provider";
import { TRPCProvider } from "@/lib/trpc";
import "./globals.css";

export const metadata: Metadata = {
  title: "GoodCart — Curated Food, Not the Algorithm",
  description:
    "Shop the food recommendations of the world's most trusted creators. Build your storefront and earn commission.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex min-h-screen flex-col">
        <AuthProvider>
          <TRPCProvider>
            <Navbar />
            <main className="flex-1">{children}</main>
            <Footer />
          </TRPCProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
