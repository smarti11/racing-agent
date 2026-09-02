import { prisma, FoodCategory, AffiliateNetwork } from "./index";

const IMG = {
  proteinBar:
    "https://images.unsplash.com/photo-1621939514649-280e2ee25f60?w=400&h=400&fit=crop",
  sparkling:
    "https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=400&h=400&fit=crop",
  oats: "https://images.unsplash.com/photo-1517673400267-025144a427c8?w=400&h=400&fit=crop",
  mealKit:
    "https://images.unsplash.com/photo-1556910103-1c02745aae4d?w=400&h=400&fit=crop",
  supplements:
    "https://images.unsplash.com/photo-1550572017-edd951aa8b74?w=400&h=400&fit=crop",
  apples:
    "https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=400&h=400&fit=crop",
  yogurt:
    "https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400&h=400&fit=crop",
  energy:
    "https://images.unsplash.com/photo-1622543925917-763c34d8a36a?w=400&h=400&fit=crop",
  figBars:
    "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?w=400&h=400&fit=crop",
  avocado:
    "https://images.unsplash.com/photo-1523049673857-eb18f1ebb7f5?w=400&h=400&fit=crop",
  pasta:
    "https://images.unsplash.com/photo-1551462147-ff29053edda2?w=400&h=400&fit=crop",
  frozen:
    "https://images.unsplash.com/photo-1574484284002-952d92456975?w=400&h=400&fit=crop",
};

const SAMPLE_PRODUCTS = [
  {
    id: "seed-B01K2S5D8G",
    name: "RXBAR Chocolate Sea Salt Protein Bar",
    brand: "RXBAR",
    sourceUrl: "https://www.amazon.com/dp/B01K2S5D8G",
    retailer: "amazon",
    retailerId: "B01K2S5D8G",
    category: FoodCategory.SNACKS,
    dietaryTags: '["gluten-free","high-protein"]',
    priceCents: 2499,
    imageUrl: IMG.proteinBar,
  },
  {
    id: "seed-B00O79SKV6",
    name: "La Croix Sparkling Water Variety Pack",
    brand: "LaCroix",
    sourceUrl: "https://www.amazon.com/dp/B00O79SKV6",
    retailer: "amazon",
    retailerId: "B00O79SKV6",
    category: FoodCategory.BEVERAGES,
    dietaryTags: '["vegan","sugar-free"]',
    priceCents: 1999,
    imageUrl: IMG.sparkling,
  },
  {
    id: "seed-B004VLVB5C",
    name: "Bob's Red Mill Organic Rolled Oats",
    brand: "Bob's Red Mill",
    sourceUrl: "https://www.amazon.com/dp/B004VLVB5C",
    retailer: "amazon",
    retailerId: "B004VLVB5C",
    category: FoodCategory.PANTRY,
    dietaryTags: '["organic","vegan"]',
    priceCents: 1299,
    imageUrl: IMG.oats,
  },
  {
    id: "seed-mediterranean-kit",
    name: "Blue Apron Meal Kit - Mediterranean",
    brand: "Blue Apron",
    sourceUrl: "https://www.blueapron.com/",
    retailer: "blueapron",
    retailerId: "mediterranean-kit",
    category: FoodCategory.MEAL_KITS,
    dietaryTags: '["mediterranean"]',
    priceCents: 5999,
    imageUrl: IMG.mealKit,
  },
  {
    id: "seed-B08N5WRWNW",
    name: "Athletic Greens AG1",
    brand: "Athletic Greens",
    sourceUrl: "https://www.amazon.com/dp/B08N5WRWNW",
    retailer: "amazon",
    retailerId: "B08N5WRWNW",
    category: FoodCategory.SUPPLEMENTS,
    dietaryTags: '["vegan","gluten-free"]',
    priceCents: 9900,
    imageUrl: IMG.supplements,
  },
  {
    id: "seed-B00EXAMPLE1",
    name: "Organic Honeycrisp Apples",
    brand: "Whole Foods",
    sourceUrl: "https://www.amazon.com/dp/B00EXAMPLE1",
    retailer: "amazon",
    retailerId: "B00EXAMPLE1",
    category: FoodCategory.PRODUCE,
    dietaryTags: '["organic"]',
    priceCents: 499,
    imageUrl: IMG.apples,
  },
  {
    id: "seed-B00EXAMPLE2",
    name: "Chobani Greek Yogurt Variety Pack",
    brand: "Chobani",
    sourceUrl: "https://www.amazon.com/dp/B00EXAMPLE2",
    retailer: "amazon",
    retailerId: "B00EXAMPLE2",
    category: FoodCategory.DAIRY,
    dietaryTags: '["high-protein"]',
    priceCents: 599,
    imageUrl: IMG.yogurt,
  },
  {
    id: "seed-B00EXAMPLE3",
    name: "Celsius Sparkling Energy Drink",
    brand: "Celsius",
    sourceUrl: "https://www.amazon.com/dp/B00EXAMPLE3",
    retailer: "amazon",
    retailerId: "B00EXAMPLE3",
    category: FoodCategory.BEVERAGES,
    dietaryTags: '["sugar-free","energy"]',
    priceCents: 2499,
    imageUrl: IMG.energy,
  },
  {
    id: "seed-B00EXAMPLE4",
    name: "Nature's Bakery Fig Bars",
    brand: "Nature's Bakery",
    sourceUrl: "https://www.amazon.com/dp/B00EXAMPLE4",
    retailer: "amazon",
    retailerId: "B00EXAMPLE4",
    category: FoodCategory.BAKERY,
    dietaryTags: '["vegan"]',
    priceCents: 549,
    imageUrl: IMG.figBars,
  },
  {
    id: "seed-B00EXAMPLE5",
    name: "Organic Hass Avocados",
    brand: "Whole Foods",
    sourceUrl: "https://www.amazon.com/dp/B00EXAMPLE5",
    retailer: "amazon",
    retailerId: "B00EXAMPLE5",
    category: FoodCategory.PRODUCE,
    dietaryTags: '["organic","vegan"]',
    priceCents: 399,
    imageUrl: IMG.avocado,
  },
  {
    id: "seed-B00EXAMPLE6",
    name: "Banza Chickpea Pasta",
    brand: "Banza",
    sourceUrl: "https://www.amazon.com/dp/B00EXAMPLE6",
    retailer: "amazon",
    retailerId: "B00EXAMPLE6",
    category: FoodCategory.PANTRY,
    dietaryTags: '["gluten-free","high-protein"]',
    priceCents: 449,
    imageUrl: IMG.pasta,
  },
  {
    id: "seed-B00EXAMPLE7",
    name: "Amy's Organic Burrito Bowl",
    brand: "Amy's",
    sourceUrl: "https://www.amazon.com/dp/B00EXAMPLE7",
    retailer: "amazon",
    retailerId: "B00EXAMPLE7",
    category: FoodCategory.FROZEN,
    dietaryTags: '["organic","vegetarian"]',
    priceCents: 599,
    imageUrl: IMG.frozen,
  },
];

const CREATORS = [
  {
    email: "creator@goodcart.demo",
    handle: "grocerygirl",
    name: "Grocery Girl",
    bio: "Your guide to every grocery aisle — from morning oats to late-night snacks.",
    avatarUrl:
      "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=200&h=200&fit=crop",
    instagramUrl: "https://instagram.com/grocerygirl",
    tiktokUrl: "https://tiktok.com/@grocerygirl",
    collections: [
      {
        id: "seed-collection-morning",
        name: "Morning Routine",
        description: "What I reach for every morning",
        productIds: [
          "seed-B004VLVB5C",
          "seed-B00O79SKV6",
          "seed-B08N5WRWNW",
        ],
      },
      {
        id: "seed-collection-snacks",
        name: "Snack Attack",
        description: "Bars, treats, and guilt-free munchies",
        productIds: ["seed-B01K2S5D8G", "seed-B00EXAMPLE4"],
      },
    ],
    extraProductIds: ["seed-B00EXAMPLE1", "seed-mediterranean-kit"],
  },
  {
    email: "fitfuel@goodcart.demo",
    handle: "fitfuel",
    name: "Fit Fuel",
    bio: "Supplements, protein, and performance nutrition for active lifestyles.",
    avatarUrl:
      "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=200&h=200&fit=crop",
    instagramUrl: "https://instagram.com/fitfuel",
    tiktokUrl: "https://tiktok.com/@fitfuel",
    collections: [
      {
        id: "seed-collection-wellness",
        name: "Wellness Shelf",
        description: "Daily supplements and greens",
        productIds: ["seed-B08N5WRWNW", "seed-B01K2S5D8G"],
      },
      {
        id: "seed-collection-fuel",
        name: "Pre-Workout Fuel",
        description: "Energy and recovery essentials",
        productIds: ["seed-B00EXAMPLE3", "seed-B00EXAMPLE2"],
      },
    ],
    extraProductIds: ["seed-B00EXAMPLE6"],
  },
  {
    email: "pantrypro@goodcart.demo",
    handle: "pantrypro",
    name: "Pantry Pro",
    bio: "Pantry staples, meal kits, and freezer favorites for busy weeknights.",
    avatarUrl:
      "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=200&h=200&fit=crop",
    instagramUrl: "https://instagram.com/pantrypro",
    collections: [
      {
        id: "seed-collection-pantry",
        name: "Pantry Essentials",
        description: "The staples I always restock",
        productIds: ["seed-B004VLVB5C", "seed-B00EXAMPLE6"],
      },
      {
        id: "seed-collection-freezer",
        name: "Freezer Favorites",
        description: "Quick meals for busy nights",
        productIds: ["seed-B00EXAMPLE7", "seed-mediterranean-kit"],
      },
    ],
    extraProductIds: ["seed-B00EXAMPLE5", "seed-B00EXAMPLE1"],
  },
];

async function main() {
  console.log("Seeding database...");

  for (const p of SAMPLE_PRODUCTS) {
    const { id, ...data } = p;
    await prisma.product.upsert({
      where: { id },
      update: { imageUrl: data.imageUrl, priceCents: data.priceCents },
      create: { id, ...data },
    });

    await prisma.affiliateOffer.upsert({
      where: { id: `offer-${id}` },
      update: {},
      create: {
        id: `offer-${id}`,
        productId: id,
        network: AffiliateNetwork.AMAZON,
        commissionRate: 0.08,
        affiliateUrlTemplate: `https://www.amazon.com/dp/${data.retailerId}?tag={{TAG}}&linkCode=ogi&th=1&psc=1`,
        networkProductId: data.retailerId,
      },
    });
  }

  for (const c of CREATORS) {
    const existing = await prisma.user.findUnique({ where: { handle: c.handle } });
    const creator = existing
      ? await prisma.user.update({
          where: { id: existing.id },
          data: {
            email: c.email,
            name: c.name,
            bio: c.bio,
            avatarUrl: c.avatarUrl,
            instagramUrl: c.instagramUrl,
            tiktokUrl: c.tiktokUrl ?? null,
            role: "CREATOR",
          },
        })
      : await prisma.user.upsert({
          where: { email: c.email },
          update: {
            name: c.name,
            handle: c.handle,
            bio: c.bio,
            avatarUrl: c.avatarUrl,
            instagramUrl: c.instagramUrl,
            tiktokUrl: c.tiktokUrl ?? null,
            role: "CREATOR",
          },
          create: {
            email: c.email,
            name: c.name,
            handle: c.handle,
            bio: c.bio,
            avatarUrl: c.avatarUrl,
            role: "CREATOR",
            instagramUrl: c.instagramUrl,
            tiktokUrl: c.tiktokUrl ?? null,
            creatorProfile: { create: { applicationStatus: "APPROVED" } },
          },
        });

    await prisma.creatorProfile.upsert({
      where: { userId: creator.id },
      update: { applicationStatus: "APPROVED" },
      create: { userId: creator.id, applicationStatus: "APPROVED" },
    });

    let sortOrder = 0;
    for (const col of c.collections) {
      const collection = await prisma.collection.upsert({
        where: { id: col.id },
        update: { name: col.name, description: col.description },
        create: {
          id: col.id,
          userId: creator.id,
          name: col.name,
          description: col.description,
          visibility: "PUBLIC",
        },
      });

      for (const productId of col.productIds) {
        await prisma.creatorProduct.upsert({
          where: {
            creatorId_productId: { creatorId: creator.id, productId },
          },
          update: { collectionId: collection.id, sortOrder: sortOrder++ },
          create: {
            creatorId: creator.id,
            productId,
            collectionId: collection.id,
            note: "One of my daily staples!",
            sortOrder: sortOrder++,
            isPinned: sortOrder === 1,
          },
        });
      }
    }

    for (const productId of c.extraProductIds) {
      await prisma.creatorProduct.upsert({
        where: {
          creatorId_productId: { creatorId: creator.id, productId },
        },
        update: {},
        create: {
          creatorId: creator.id,
          productId,
          note: "Highly recommend!",
          sortOrder: sortOrder++,
        },
      });
    }
  }

  const existingConsumer = await prisma.user.findUnique({ where: { handle: "alexshop" } });
  const consumer = existingConsumer
    ? await prisma.user.update({
        where: { id: existingConsumer.id },
        data: { email: "shopper@goodcart.demo", name: "Alex Shopper" },
      })
    : await prisma.user.upsert({
        where: { email: "shopper@goodcart.demo" },
        update: {},
        create: {
          email: "shopper@goodcart.demo",
          name: "Alex Shopper",
          handle: "alexshop",
          role: "CONSUMER",
        },
      });

  const groceryGirl = await prisma.user.findUnique({
    where: { handle: "grocerygirl" },
  });
  const fitFuel = await prisma.user.findUnique({ where: { handle: "fitfuel" } });

  for (const creator of [groceryGirl, fitFuel].filter(Boolean)) {
    await prisma.follow.upsert({
      where: {
        followerId_followingId: {
          followerId: consumer.id,
          followingId: creator!.id,
        },
      },
      update: {},
      create: { followerId: consumer.id, followingId: creator!.id },
    });
  }

  console.log("Seed complete — 3 creators, 12 products, 6 collections.");
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
