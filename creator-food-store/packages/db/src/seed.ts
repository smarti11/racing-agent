import { prisma, FoodCategory, AffiliateNetwork } from "./index";

const SAMPLE_PRODUCTS = [
  {
    name: "RXBAR Chocolate Sea Salt Protein Bar",
    brand: "RXBAR",
    sourceUrl: "https://www.amazon.com/dp/B01K2S5D8G",
    retailer: "amazon",
    retailerId: "B01K2S5D8G",
    category: FoodCategory.SNACKS,
    dietaryTags: '["gluten-free","high-protein"]',
    priceCents: 2499,
    imageUrl: "https://m.media-amazon.com/images/I/81QZQZQZQZL._AC_SL1500_.jpg",
  },
  {
    name: "La Croix Sparkling Water Variety Pack",
    brand: "LaCroix",
    sourceUrl: "https://www.amazon.com/dp/B00O79SKV6",
    retailer: "amazon",
    retailerId: "B00O79SKV6",
    category: FoodCategory.BEVERAGES,
    dietaryTags: '["vegan","sugar-free"]',
    priceCents: 1999,
    imageUrl: "https://m.media-amazon.com/images/I/71abc123._AC_SL1500_.jpg",
  },
  {
    name: "Bob's Red Mill Organic Rolled Oats",
    brand: "Bob's Red Mill",
    sourceUrl: "https://www.amazon.com/dp/B004VLVB5C",
    retailer: "amazon",
    retailerId: "B004VLVB5C",
    category: FoodCategory.PANTRY,
    dietaryTags: '["organic","vegan"]',
    priceCents: 1299,
    imageUrl: "https://m.media-amazon.com/images/I/71oats._AC_SL1500_.jpg",
  },
  {
    name: "Blue Apron Meal Kit - Mediterranean",
    brand: "Blue Apron",
    sourceUrl: "https://www.blueapron.com/",
    retailer: "blueapron",
    retailerId: "mediterranean-kit",
    category: FoodCategory.MEAL_KITS,
    dietaryTags: '["mediterranean"]',
    priceCents: 5999,
  },
  {
    name: "Athletic Greens AG1",
    brand: "Athletic Greens",
    sourceUrl: "https://www.amazon.com/dp/B08N5WRWNW",
    retailer: "amazon",
    retailerId: "B08N5WRWNW",
    category: FoodCategory.SUPPLEMENTS,
    dietaryTags: '["vegan","gluten-free"]',
    priceCents: 9900,
  },
];

async function main() {
  console.log("Seeding database...");

  const creator = await prisma.user.upsert({
    where: { email: "creator@goodcart.demo" },
    update: {
      name: "Grocery Girl",
      handle: "grocerygirl",
      bio: "Sharing my favorite grocery finds, pantry staples, and snacks.",
      instagramUrl: "https://instagram.com/grocerygirl",
    },
    create: {
      email: "creator@goodcart.demo",
      name: "Grocery Girl",
      handle: "grocerygirl",
      bio: "Sharing my favorite grocery finds, pantry staples, and snacks.",
      role: "CREATOR",
      instagramUrl: "https://instagram.com/grocerygirl",
      creatorProfile: { create: { applicationStatus: "APPROVED" } },
    },
  });

  const consumer = await prisma.user.upsert({
    where: { email: "shopper@goodcart.demo" },
    update: {},
    create: {
      email: "shopper@goodcart.demo",
      name: "Alex Shopper",
      handle: "alexshop",
      role: "CONSUMER",
    },
  });

  const collection = await prisma.collection.upsert({
    where: { id: "seed-collection-1" },
    update: {},
    create: {
      id: "seed-collection-1",
      userId: creator.id,
      name: "Morning Routine",
      description: "What I reach for every morning",
      visibility: "PUBLIC",
    },
  });

  for (const p of SAMPLE_PRODUCTS) {
    const product = await prisma.product.upsert({
      where: { id: `seed-${p.retailerId}` },
      update: {},
      create: { id: `seed-${p.retailerId}`, ...p },
    });

    await prisma.affiliateOffer.upsert({
      where: { id: `offer-${product.id}` },
      update: {},
      create: {
        id: `offer-${product.id}`,
        productId: product.id,
        network: AffiliateNetwork.AMAZON,
        commissionRate: 0.08,
        affiliateUrlTemplate: `https://www.amazon.com/dp/${p.retailerId}?tag={{TAG}}&linkCode=ogi&th=1&psc=1`,
        networkProductId: p.retailerId,
      },
    });

    await prisma.creatorProduct.upsert({
      where: {
        creatorId_productId: { creatorId: creator.id, productId: product.id },
      },
      update: {},
      create: {
        creatorId: creator.id,
        productId: product.id,
        collectionId: collection.id,
        note: "One of my daily staples!",
        sortOrder: SAMPLE_PRODUCTS.indexOf(p),
      },
    });
  }

  await prisma.follow.upsert({
    where: {
      followerId_followingId: {
        followerId: consumer.id,
        followingId: creator.id,
      },
    },
    update: {},
    create: { followerId: consumer.id, followingId: creator.id },
  });

  console.log("Seed complete.");
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
