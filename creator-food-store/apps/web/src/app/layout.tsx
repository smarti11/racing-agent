import type { Metadata } from "next";
import { Navbar } from "@/components/navbar";
import { Footer } from "@/components/footer";
import { AuthProvider } from "@/components/auth-provider";
import { TRPCProvider } from "@/lib/trpc";
import "./globals.css";

export const metadata: Metadata = {
  title: "GoodCart — Curated Grocery, Not the Algorithm",
  description:
    "Shop consumable grocery products recommended by creators — food, beverages, supplements, produce, dairy, and every grocery aisle.",
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
