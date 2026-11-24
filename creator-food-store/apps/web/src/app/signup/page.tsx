import SignupForm from "./signup-form";

export default function SignupPage({
  searchParams,
}: {
  searchParams: Promise<{ role?: string }>;
}) {
  return <SignupFormWrapper searchParams={searchParams} />;
}

async function SignupFormWrapper({
  searchParams,
}: {
  searchParams: Promise<{ role?: string }>;
}) {
  const params = await searchParams;
  const defaultRole = params.role === "creator" ? "CREATOR" : "CONSUMER";
  return <SignupForm defaultRole={defaultRole} />;
}
