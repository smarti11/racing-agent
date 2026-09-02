export default function TermsPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <p className="section-label">Legal</p>
      <h1 className="mt-2 font-display text-4xl text-ink">Terms of Service</h1>
      <p className="mt-4 text-sm text-muted">Last updated: September 2, 2026</p>

      <div className="prose prose-stone mt-10 max-w-none text-muted">
        <h2 className="font-display text-xl text-ink">1. Acceptance of Terms</h2>
        <p>
          By using GoodCart, you agree to these Terms of Service. GoodCart is a
          food-only creator commerce platform that enables affiliate product
          recommendations and commission-based earnings.
        </p>

        <h2 className="mt-8 font-display text-xl text-ink">2. Creator Responsibilities</h2>
        <ul className="list-disc pl-5">
          <li>Disclose affiliate relationships per FTC guidelines on all storefronts</li>
          <li>Only add food, beverage, grocery, and related kitchen products</li>
          <li>Do not make unsubstantiated health claims about products</li>
        </ul>

        <h2 className="mt-8 font-display text-xl text-ink">3. Payouts</h2>
        <p>
          Creator payouts are processed weekly via Stripe Connect for confirmed
          commissions after a 30-day hold period.
        </p>

        <h2 className="mt-8 font-display text-xl text-ink">Contact</h2>
        <p>Email: legal@goodcart.com</p>
      </div>
    </div>
  );
}
