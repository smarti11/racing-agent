/** All consumable grocery product categories supported by GoodCart */
export const GROCERY_CATEGORIES = [
  "SNACKS",
  "BEVERAGES",
  "PANTRY",
  "PRODUCE",
  "DAIRY",
  "FROZEN",
  "DELI",
  "BAKERY",
  "MEAL_KITS",
  "SUPPLEMENTS",
  "SPECIALTY",
] as const;

export type GroceryCategory = (typeof GROCERY_CATEGORIES)[number];

/** @deprecated Use GroceryCategory */
export type FoodCategory = GroceryCategory;

export const GROCERY_CATEGORY_LABELS: Record<GroceryCategory, string> = {
  SNACKS: "Snacks",
  BEVERAGES: "Beverages",
  PANTRY: "Pantry",
  PRODUCE: "Produce",
  DAIRY: "Dairy & Eggs",
  FROZEN: "Frozen",
  DELI: "Deli & Prepared",
  BAKERY: "Bakery",
  MEAL_KITS: "Meal Kits",
  SUPPLEMENTS: "Supplements",
  SPECIALTY: "Specialty",
};

export const CONSUMABLE_SCOPE_DESCRIPTION =
  "Any single consumable product found at a grocery store — food, beverages, supplements, produce, dairy, frozen, deli, bakery, and pantry items.";
