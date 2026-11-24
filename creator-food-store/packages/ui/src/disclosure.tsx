export function AffiliateDisclosure({ className }: { className?: string }) {
  return (
    <p
      className={`text-xs text-stone-500 ${className ?? ""}`}
      role="note"
      aria-label="Affiliate disclosure"
    >
      As an affiliate, I earn commission from qualifying purchases. Prices and
      availability are subject to change.
    </p>
  );
}
