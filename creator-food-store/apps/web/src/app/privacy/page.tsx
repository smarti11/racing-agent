export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <p className="section-label">Legal</p>
      <h1 className="mt-2 font-display text-4xl text-ink">Privacy Policy</h1>
      <p className="mt-4 text-sm text-muted">Last updated: September 2, 2026</p>

      <div className="prose prose-stone mt-10 max-w-none text-muted">
        <h2 className="font-display text-xl text-ink">Information We Collect</h2>
        <p>
          GoodCart collects information you provide when creating an account (name,
          email, handle), social profile links, and product curation activity. We
          also collect click and conversion data for affiliate attribution.
        </p>

        <h2 className="mt-8 font-display text-xl text-ink">How We Use Your Information</h2>
        <ul className="list-disc pl-5">
          <li>To operate your creator storefront and consumer cart</li>
          <li>To track affiliate commissions and process payouts</li>
          <li>To send price alert notifications</li>
          <li>To improve our platform and prevent fraud</li>
        </ul>

        <h2 className="mt-8 font-display text-xl text-ink">Third-Party Services</h2>
        <p>
          We use Stripe for payment processing, affiliate networks (Amazon
          Associates, Impact) for commission tracking, and OAuth providers (Google,
          Instagram, TikTok) for authentication.
        </p>

        <h2 className="mt-8 font-display text-xl text-ink">Contact</h2>
        <p>Email: privacy@goodcart.com</p>
      </div>
    </div>
  );
}
