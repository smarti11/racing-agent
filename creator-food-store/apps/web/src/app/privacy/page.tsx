export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12 prose prose-stone">
      <h1>Privacy Policy</h1>
      <p>Last updated: September 2, 2026</p>

      <h2>Information We Collect</h2>
      <p>
        PantryLink collects information you provide when creating an account (name,
        email, handle), social profile links, and product curation activity. We
        also collect click and conversion data for affiliate attribution.
      </p>

      <h2>How We Use Your Information</h2>
      <ul>
        <li>To operate your creator storefront and consumer locker</li>
        <li>To track affiliate commissions and process payouts</li>
        <li>To send price alert notifications</li>
        <li>To improve our platform and prevent fraud</li>
      </ul>

      <h2>Third-Party Services</h2>
      <p>
        We use Stripe for payment processing, affiliate networks (Amazon
        Associates, Impact) for commission tracking, and OAuth providers (Google,
        Instagram, TikTok) for authentication. Each service has its own privacy
        policy.
      </p>

      <h2>Your Rights</h2>
      <p>
        You may request access to, correction of, or deletion of your personal
        data by contacting support@pantrylink.com. California and EU residents
        have additional rights under CCPA and GDPR.
      </p>

      <h2>Contact</h2>
      <p>Email: privacy@pantrylink.com</p>
    </div>
  );
}
