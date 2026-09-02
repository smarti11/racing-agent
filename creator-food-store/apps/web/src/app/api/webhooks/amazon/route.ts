import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@repo/db";
import { parseSubId } from "@repo/affiliate-engine";

export async function GET(req: NextRequest) {
  const params = req.nextUrl.searchParams;
  const orderId = params.get("orderId") ?? params.get("tag");
  const amount = parseFloat(params.get("amount") ?? "0");
  const commission = parseFloat(params.get("commission") ?? "0");
  const subId = params.get("ascsubtag") ?? params.get("subId");

  if (!orderId || !subId) {
    return NextResponse.json({ error: "Missing params" }, { status: 400 });
  }

  const parsed = parseSubId(subId);
  if (!parsed) {
    return NextResponse.json({ error: "Invalid subId" }, { status: 400 });
  }

  const creator = await prisma.user.findFirst({
    where: { id: { startsWith: parsed.creatorIdPrefix } },
  });
  const product = await prisma.product.findFirst({
    where: { id: { startsWith: parsed.productIdPrefix } },
  });

  if (!creator || !product) {
    return NextResponse.json({ error: "Attribution not found" }, { status: 404 });
  }

  const link = await prisma.trackedLink.findFirst({
    where: { creatorId: creator.id, productId: product.id },
    orderBy: { createdAt: "desc" },
  });

  const conversion = await prisma.conversion.upsert({
    where: {
      network_networkOrderId: { network: "AMAZON", networkOrderId: orderId },
    },
    update: { commission, orderAmount: amount, status: "CONFIRMED", confirmedAt: new Date() },
    create: {
      linkId: link?.id,
      creatorId: creator.id,
      productId: product.id,
      networkOrderId: orderId,
      network: "AMAZON",
      orderAmount: amount,
      commission,
      status: "CONFIRMED",
      subId,
      confirmedAt: new Date(),
    },
  });

  await prisma.creatorProfile.update({
    where: { userId: creator.id },
    data: {
      pendingEarnings: { increment: commission },
      totalEarnings: { increment: commission },
    },
  });

  return NextResponse.json({ success: true, conversionId: conversion.id });
}
