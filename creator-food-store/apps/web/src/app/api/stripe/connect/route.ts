import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { prisma } from "@repo/db";
import Stripe from "stripe";

const stripe = process.env.STRIPE_SECRET_KEY
  ? new Stripe(process.env.STRIPE_SECRET_KEY)
  : null;

export async function POST() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  if (!stripe) {
    return NextResponse.json(
      { error: "Stripe not configured", demo: true },
      { status: 200 }
    );
  }

  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    include: { creatorProfile: true },
  });

  if (!user?.creatorProfile) {
    return NextResponse.json({ error: "Creator profile required" }, { status: 400 });
  }

  let accountId = user.creatorProfile.stripeConnectId;

  if (!accountId) {
    const account = await stripe.accounts.create({
      type: "express",
      email: user.email,
      metadata: { userId: user.id },
      capabilities: {
        transfers: { requested: true },
      },
    });
    accountId = account.id;
    await prisma.creatorProfile.update({
      where: { userId: user.id },
      data: { stripeConnectId: accountId },
    });
  }

  const accountLink = await stripe.accountLinks.create({
    account: accountId,
    refresh_url: `${process.env.NEXT_PUBLIC_APP_URL}/dashboard`,
    return_url: `${process.env.NEXT_PUBLIC_APP_URL}/dashboard?stripe=success`,
    type: "account_onboarding",
  });

  return NextResponse.json({ url: accountLink.url });
}
