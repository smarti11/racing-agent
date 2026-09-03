import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@repo/db";
import { parseSubId } from "@repo/affiliate-engine";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const {
      orderId,
      amount,
      commission,
      subId,
      status = "pending",
    } = body as {
      orderId: string;
      amount: number;
      commission: number;
      subId: string;
      status?: string;
    };

    if (!orderId || !subId) {
      return NextResponse.json({ error: "Missing required fields" }, { status: 400 });
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

    const conversionStatus =
      status === "confirmed" ? "CONFIRMED" : status === "reversed" ? "REVERSED" : "PENDING";

    const conversion = await prisma.conversion.upsert({
      where: {
        network_networkOrderId: { network: "IMPACT", networkOrderId: orderId },
      },
      update: {
        status: conversionStatus,
        commission,
        orderAmount: amount,
        confirmedAt: conversionStatus === "CONFIRMED" ? new Date() : undefined,
      },
      create: {
        linkId: link?.id,
        creatorId: creator.id,
        productId: product.id,
        networkOrderId: orderId,
        network: "IMPACT",
        orderAmount: amount,
        commission,
        status: conversionStatus,
        subId,
        confirmedAt: conversionStatus === "CONFIRMED" ? new Date() : undefined,
      },
    });

    if (conversionStatus === "CONFIRMED") {
      await prisma.creatorProfile.update({
        where: { userId: creator.id },
        data: {
          pendingEarnings: { increment: commission },
          totalEarnings: { increment: commission },
        },
      });
    }

    return NextResponse.json({ success: true, conversionId: conversion.id });
  } catch (error) {
    console.error("Impact webhook error:", error);
    return NextResponse.json({ error: "Internal error" }, { status: 500 });
  }
}
