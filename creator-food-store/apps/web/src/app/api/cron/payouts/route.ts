import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@repo/db";
import Stripe from "stripe";

const stripe = process.env.STRIPE_SECRET_KEY
  ? new Stripe(process.env.STRIPE_SECRET_KEY)
  : null;

export async function POST(req: NextRequest) {
  if (!stripe) {
    return NextResponse.json({ received: true, demo: true });
  }

  const body = await req.text();
  const sig = req.headers.get("stripe-signature");

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(
      body,
      sig!,
      process.env.STRIPE_WEBHOOK_SECRET!
    );
  } catch {
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  if (event.type === "account.updated") {
    const account = event.data.object as Stripe.Account;
    if (account.charges_enabled && account.payouts_enabled) {
      await prisma.creatorProfile.updateMany({
        where: { stripeConnectId: account.id },
        data: { stripeOnboarded: true },
      });
    }
  }

  return NextResponse.json({ received: true });
}

export async function GET() {
  await runWeeklyPayouts();
  return NextResponse.json({ success: true, message: "Payout job completed" });
}

async function runWeeklyPayouts() {
  if (!stripe) return;

  const periodEnd = new Date();
  const periodStart = new Date();
  periodStart.setDate(periodStart.getDate() - 7);

  const creators = await prisma.creatorProfile.findMany({
    where: { stripeOnboarded: true, pendingEarnings: { gt: 0 } },
    include: { user: true },
  });

  for (const profile of creators) {
    const holdDate = new Date();
    holdDate.setDate(holdDate.getDate() - 30);

    const eligible = await prisma.conversion.aggregate({
      where: {
        creatorId: profile.userId,
        status: "CONFIRMED",
        confirmedAt: { lte: holdDate },
        createdAt: { gte: periodStart, lte: periodEnd },
      },
      _sum: { commission: true },
    });

    const amount = eligible._sum.commission ?? 0;
    if (amount < 1 || !profile.stripeConnectId) continue;

    try {
      const transfer = await stripe.transfers.create({
        amount: Math.round(amount * 100),
        currency: "usd",
        destination: profile.stripeConnectId,
        metadata: { userId: profile.userId },
      });

      await prisma.earning.create({
        data: {
          creatorId: profile.userId,
          amount,
          periodStart,
          periodEnd,
          status: "PAID",
          stripeTransferId: transfer.id,
          paidAt: new Date(),
        },
      });

      await prisma.creatorProfile.update({
        where: { userId: profile.userId },
        data: { pendingEarnings: { decrement: amount } },
      });
    } catch (error) {
      console.error(`Payout failed for ${profile.userId}:`, error);
      await prisma.earning.create({
        data: {
          creatorId: profile.userId,
          amount,
          periodStart,
          periodEnd,
          status: "FAILED",
        },
      });
    }
  }
}
