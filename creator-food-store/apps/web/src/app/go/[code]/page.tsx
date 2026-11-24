import { prisma } from "@repo/db";
import { notFound, redirect } from "next/navigation";
import { headers } from "next/headers";
import { createHash } from "crypto";

interface Props {
  params: Promise<{ code: string }>;
}

export default async function GoRedirectPage({ params }: Props) {
  const { code } = await params;

  const link = await prisma.trackedLink.findUnique({
    where: { shortCode: code },
    include: { offer: true },
  });

  if (!link) notFound();

  const headersList = await headers();
  const referrer = headersList.get("referer") ?? undefined;
  const userAgent = headersList.get("user-agent") ?? undefined;
  const ip = headersList.get("x-forwarded-for") ?? headersList.get("x-real-ip") ?? "";
  const ipHash = ip ? createHash("sha256").update(ip).digest("hex").slice(0, 16) : undefined;

  await prisma.$transaction([
    prisma.click.create({
      data: {
        linkId: link.id,
        referrer,
        userAgent,
        ipHash,
      },
    }),
    prisma.trackedLink.update({
      where: { id: link.id },
      data: { clickCount: { increment: 1 } },
    }),
  ]);

  redirect(link.destinationUrl);
}
