import { NextResponse } from "next/server";
import { prisma } from "@repo/db";

export async function GET() {
  const alerts = await prisma.priceAlert.findMany({
    where: { status: "ACTIVE" },
    include: { product: true },
  });

  let triggered = 0;

  for (const alert of alerts) {
    const currentPrice = alert.product.priceCents;
    if (!currentPrice) continue;

    if (currentPrice <= alert.targetPriceCents) {
      await prisma.priceAlert.update({
        where: { id: alert.id },
        data: {
          status: "TRIGGERED",
          notifiedAt: new Date(),
          lastCheckedAt: new Date(),
        },
      });
      triggered++;
    } else {
      await prisma.priceAlert.update({
        where: { id: alert.id },
        data: { lastCheckedAt: new Date() },
      });
    }
  }

  return NextResponse.json({
    checked: alerts.length,
    triggered,
  });
}
