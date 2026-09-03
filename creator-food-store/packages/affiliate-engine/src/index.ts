import type { GroceryCategory } from "./categories";

export * from "./categories";

export type AffiliateNetwork =
  | "AMAZON"
  | "IMPACT"
  | "CJ"
  | "SHAREASALE"
  | "RAKUTEN"
  | "DIRECT"
  | "SKIMLINKS";

export interface ResolvedProduct {
  name: string;
  brand?: string;
  retailer: string;
  retailerId?: string;
  sourceUrl: string;
  category: GroceryCategory;
  imageUrl?: string;
  priceCents?: number;
}

export interface AffiliateOfferResult {
  network: AffiliateNetwork;
  commissionRate: number;
  destinationUrl: string;
  networkProductId?: string;
}

export interface MonetizeInput {
  url: string;
  creatorId: string;
  productId: string;
  amazonTag?: string;
  impactMediaPartnerId?: string;
}

export interface MonetizeResult {
  product: ResolvedProduct;
  offer: AffiliateOfferResult;
  subId: string;
}

/** Grocery & consumable retailers */
const GROCERY_RETAILERS = new Set([
  "amazon",
  "walmart",
  "instacart",
  "thrivemarket",
  "iherb",
  "vitacost",
  "wholefoods",
  "target",
  "kroger",
  "costco",
  "samsclub",
  "safeway",
  "albertsons",
  "heb",
  "publix",
  "freshdirect",
  "blueapron",
  "hellofresh",
  "butcherbox",
  "imperfectfoods",
  "gopuff",
  "sprouts",
]);

const BLOCKED_RETAILERS = new Set([
  "nordstrom",
  "zara",
  "sephora",
  "ulta",
  "nike",
  "adidas",
  "bestbuy",
  "homedepot",
  "lowes",
]);

/** Keywords that indicate a non-consumable product (blocked) */
const NON_CONSUMABLE_KEYWORDS = [
  "cookware",
  "frying pan",
  "skillet",
  "knife set",
  "cutting board",
  "blender",
  "air fryer",
  "instant pot",
  "microwave oven",
  "toaster",
  "coffee maker",
  "food processor",
  "mixing bowl",
  "storage container",
  "tupperware",
  "laundry detergent",
  "dish soap",
  "paper towel",
  "toilet paper",
  "cleaning spray",
  "shampoo",
  "conditioner",
  "moisturizer",
  "lipstick",
  "mascara",
  "t-shirt",
  "sneakers",
  "phone case",
  "laptop",
  "furniture",
  "pet toy",
  "dog leash",
  "cat litter",
];

const RETAILER_PATTERNS: Array<{
  pattern: RegExp;
  retailer: string;
  extractId: (url: URL) => string | undefined;
}> = [
  {
    pattern: /amazon\.(com|co\.uk|ca)/i,
    retailer: "amazon",
    extractId: (url) => {
      const dp = url.pathname.match(/\/dp\/([A-Z0-9]{10})/i);
      if (dp) return dp[1];
      const gp = url.pathname.match(/\/gp\/product\/([A-Z0-9]{10})/i);
      return gp?.[1];
    },
  },
  {
    pattern: /walmart\.com/i,
    retailer: "walmart",
    extractId: (url) => url.pathname.match(/\/ip\/[^/]+\/(\d+)/)?.[1],
  },
  {
    pattern: /instacart\.com/i,
    retailer: "instacart",
    extractId: (url) => url.pathname.split("/").pop(),
  },
  {
    pattern: /thrivemarket\.com/i,
    retailer: "thrivemarket",
    extractId: (url) => url.pathname.split("/").pop(),
  },
  {
    pattern: /iherb\.com/i,
    retailer: "iherb",
    extractId: (url) => url.pathname.match(/\/pr\/[^/]+\/(\d+)/)?.[1],
  },
  {
    pattern: /vitacost\.com/i,
    retailer: "vitacost",
    extractId: (url) => url.pathname.match(/\/(\d+)$/)?.[1],
  },
  {
    pattern: /kroger\.com/i,
    retailer: "kroger",
    extractId: (url) => url.pathname.match(/\/p\/[^/]+\/(\d+)/)?.[1],
  },
  {
    pattern: /costco\.com/i,
    retailer: "costco",
    extractId: (url) => url.pathname.match(/\.product\.(\d+)/)?.[1],
  },
  {
    pattern: /samsclub\.com/i,
    retailer: "samsclub",
    extractId: (url) => url.pathname.match(/\/ip\/[^/]+\/(\d+)/)?.[1],
  },
  {
    pattern: /safeway\.com/i,
    retailer: "safeway",
    extractId: (url) => url.pathname.split("/").pop(),
  },
  {
    pattern: /albertsons\.com/i,
    retailer: "albertsons",
    extractId: (url) => url.pathname.split("/").pop(),
  },
  {
    pattern: /heb\.com/i,
    retailer: "heb",
    extractId: (url) => url.pathname.split("/").pop(),
  },
  {
    pattern: /publix\.com/i,
    retailer: "publix",
    extractId: (url) => url.pathname.split("/").pop(),
  },
  {
    pattern: /freshdirect\.com/i,
    retailer: "freshdirect",
    extractId: (url) => url.pathname.split("/").pop(),
  },
  {
    pattern: /gopuff\.com/i,
    retailer: "gopuff",
    extractId: (url) => url.pathname.split("/").pop(),
  },
  {
    pattern: /sprouts\.com/i,
    retailer: "sprouts",
    extractId: (url) => url.pathname.split("/").pop(),
  },
  {
    pattern: /blueapron\.com/i,
    retailer: "blueapron",
    extractId: (url) => url.pathname.replace(/^\//, ""),
  },
  {
    pattern: /target\.com/i,
    retailer: "target",
    extractId: (url) => url.pathname.match(/A-(\d+)/)?.[1],
  },
];

const CATEGORY_KEYWORDS: Record<GroceryCategory, string[]> = {
  SNACKS: [
    "bar", "chip", "snack", "cookie", "cracker", "nuts", "popcorn", "trail mix",
    "granola bar", "jerky", "candy", "chocolate",
  ],
  BEVERAGES: [
    "water", "coffee", "tea", "juice", "drink", "soda", "kombucha", "seltzer",
    "sparkling water", "energy drink", "sports drink", "lemonade", "milk",
    "almond milk", "oat milk", "protein shake", "smoothie", "beer", "wine",
    "cocktail", "espresso", "cold brew", "hydration",
  ],
  PANTRY: [
    "oat", "flour", "oil", "sauce", "spice", "rice", "pasta", "bean", "cereal",
    "honey", "jam", "peanut butter", "vinegar", "broth", "stock", "canned",
    "soup", "tuna", "salsa", "mustard", "ketchup", "mayo", "seasoning",
  ],
  PRODUCE: [
    "apple", "banana", "berry", "lettuce", "spinach", "kale", "tomato", "avocado",
    "onion", "potato", "carrot", "broccoli", "fruit", "vegetable", "organic produce",
    "salad", "herbs", "citrus", "melon", "grape", "mushroom",
  ],
  DAIRY: [
    "milk", "cheese", "yogurt", "butter", "cream", "egg", "cottage cheese",
    "sour cream", "cream cheese", "kefir", "ghee",
  ],
  FROZEN: [
    "frozen", "ice cream", "popsicle", "frozen pizza", "frozen meal",
    "frozen vegetable", "frozen fruit", "frozen waffle", "gelato", "sorbet",
  ],
  DELI: [
    "deli", "rotisserie", "prepared", "hummus", "guacamole", "sushi", "sandwich",
    "salad kit", "charcuterie", "olives", "dip",
  ],
  BAKERY: [
    "bread", "bagel", "muffin", "croissant", "tortilla", "bun", "roll",
    "cake", "pastry", "donut", "doughnut", "pita",
  ],
  MEAL_KITS: [
    "meal kit", "meal-kit", "blue apron", "hello fresh", "dinner kit",
    "recipe kit", "subscription box",
  ],
  SUPPLEMENTS: [
    "vitamin", "supplement", "protein powder", "ag1", "greens", "collagen",
    "probiotic", "omega", "multivitamin", "creatine", "electrolyte",
    "fish oil", "magnesium", "zinc", "ashwagandha", "turmeric", "capsule",
    "tablet", "gummy vitamin", "prebiotic", "fiber supplement", "bcaa",
    "whey", "plant protein", "superfood",
  ],
  SPECIALTY: [
    "gourmet", "artisan", "organic", "specialty", "gluten-free", "vegan",
    "keto", "paleo", "imported", "fair trade",
  ],
};

export function parseUrl(rawUrl: string): URL {
  try {
    const url = new URL(rawUrl.trim());
    if (!["http:", "https:"].includes(url.protocol)) {
      throw new Error("Invalid URL protocol");
    }
    return url;
  } catch {
    throw new Error("Invalid product URL");
  }
}

export function identifyRetailer(url: URL): { retailer: string; retailerId?: string } | null {
  for (const { pattern, retailer, extractId } of RETAILER_PATTERNS) {
    if (pattern.test(url.hostname + url.pathname)) {
      return { retailer, retailerId: extractId(url) };
    }
  }
  return null;
}

/** @deprecated Use isGroceryRetailer */
export function isFoodRetailer(retailer: string): boolean {
  return isGroceryRetailer(retailer);
}

export function isGroceryRetailer(retailer: string): boolean {
  if (BLOCKED_RETAILERS.has(retailer)) return false;
  return GROCERY_RETAILERS.has(retailer);
}

export function isConsumableProduct(url: URL, title?: string): boolean {
  const haystack = `${url.pathname} ${title ?? ""}`.toLowerCase();
  return !NON_CONSUMABLE_KEYWORDS.some((kw) => haystack.includes(kw));
}

export function inferCategory(url: URL, title?: string): GroceryCategory {
  const haystack = `${url.pathname} ${title ?? ""}`.toLowerCase();
  for (const [category, keywords] of Object.entries(CATEGORY_KEYWORDS) as [
    GroceryCategory,
    string[],
  ][]) {
    if (keywords.some((kw) => haystack.includes(kw))) return category;
  }
  return "SPECIALTY";
}

export function buildSubId(creatorId: string, productId: string): string {
  return `${creatorId.slice(0, 8)}_${productId.slice(0, 8)}`;
}

export function buildAmazonAffiliateUrl(
  retailerId: string,
  tag: string,
  subId: string
): string {
  const params = new URLSearchParams({
    tag,
    linkCode: "ogi",
    th: "1",
    psc: "1",
    ascsubtag: subId,
  });
  return `https://www.amazon.com/dp/${retailerId}?${params.toString()}`;
}

export function buildImpactAffiliateUrl(
  baseUrl: string,
  mediaPartnerId: string,
  subId: string
): string {
  const params = new URLSearchParams({
    u: baseUrl,
    subId1: subId,
  });
  return `https://goto.target.com/c/${mediaPartnerId}/?${params.toString()}`;
}

export function resolveProductFromUrl(url: string, titleHint?: string): ResolvedProduct {
  const parsed = parseUrl(url);
  const identified = identifyRetailer(parsed);

  if (!identified) {
    throw new Error(
      "Unsupported retailer. GoodCart supports grocery stores including Amazon, Walmart, Instacart, Kroger, Costco, Target, iHerb, Vitacost, and more."
    );
  }

  if (!isGroceryRetailer(identified.retailer)) {
    throw new Error(
      "Only consumable grocery products are supported — food, beverages, supplements, and items from any grocery aisle."
    );
  }

  if (!isConsumableProduct(parsed, titleHint)) {
    throw new Error(
      "This product doesn't appear to be consumable. GoodCart is for grocery items you eat or drink — not cookware, cleaning supplies, or personal care."
    );
  }

  const category = inferCategory(parsed, titleHint);
  const slug = parsed.pathname.split("/").filter(Boolean).pop() ?? "product";

  return {
    name: titleHint || slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    retailer: identified.retailer,
    retailerId: identified.retailerId,
    sourceUrl: parsed.toString(),
    category,
  };
}

export function findBestOffer(
  product: ResolvedProduct,
  options: { amazonTag?: string; impactMediaPartnerId?: string; subId: string }
): AffiliateOfferResult {
  if (product.retailer === "amazon" && product.retailerId && options.amazonTag) {
    return {
      network: "AMAZON",
      commissionRate: 0.08,
      destinationUrl: buildAmazonAffiliateUrl(
        product.retailerId,
        options.amazonTag,
        options.subId
      ),
      networkProductId: product.retailerId,
    };
  }

  if (options.impactMediaPartnerId) {
    return {
      network: "IMPACT",
      commissionRate: 0.1,
      destinationUrl: buildImpactAffiliateUrl(
        product.sourceUrl,
        options.impactMediaPartnerId,
        options.subId
      ),
      networkProductId: product.retailerId,
    };
  }

  return {
    network: "DIRECT",
    commissionRate: 0.05,
    destinationUrl: product.sourceUrl,
    networkProductId: product.retailerId,
  };
}

export function monetizeUrl(input: MonetizeInput & { titleHint?: string }): MonetizeResult {
  const product = resolveProductFromUrl(input.url, input.titleHint);
  const subId = buildSubId(input.creatorId, input.productId);
  const offer = findBestOffer(product, {
    amazonTag: input.amazonTag,
    impactMediaPartnerId: input.impactMediaPartnerId,
    subId,
  });
  return { product, offer, subId };
}

export function generateShortCode(): string {
  const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  let code = "";
  for (let i = 0; i < 8; i++) {
    code += chars[Math.floor(Math.random() * chars.length)];
  }
  return code;
}

export function parseSubId(subId: string): { creatorIdPrefix: string; productIdPrefix: string } | null {
  const parts = subId.split("_");
  if (parts.length !== 2) return null;
  return { creatorIdPrefix: parts[0], productIdPrefix: parts[1] };
}
