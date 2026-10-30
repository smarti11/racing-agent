import { cn } from "@repo/ui";

interface LogoProps {
  className?: string;
  showWordmark?: boolean;
  size?: "sm" | "md" | "lg";
}

const sizes = {
  sm: { icon: 28, text: "text-lg" },
  md: { icon: 36, text: "text-2xl" },
  lg: { icon: 52, text: "text-4xl" },
};

export function LogoMark({
  size = 36,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden
    >
      <rect width="48" height="48" rx="12" fill="#1B7F5C" />
      <path
        d="M14 18h20l-2 14H16L14 18z"
        stroke="white"
        strokeWidth="2.2"
        strokeLinejoin="round"
        fill="none"
      />
      <path
        d="M18 18V15a6 6 0 0 1 12 0v3"
        stroke="white"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
      <circle cx="20" cy="36" r="2" fill="#A8E6CF" />
      <circle cx="30" cy="36" r="2" fill="#A8E6CF" />
      <path
        d="M30 12c2 0 4 1.5 4.5 3.5"
        stroke="#A8E6CF"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="M32.5 10.5c1.2 1.5 1.8 3.2 1.5 5"
        stroke="#A8E6CF"
        strokeWidth="1.5"
        strokeLinecap="round"
        opacity="0.7"
      />
    </svg>
  );
}

export function Logo({ className, showWordmark = true, size = "md" }: LogoProps) {
  const { icon, text } = sizes[size];

  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark size={icon} />
      {showWordmark && (
        <span className={cn("font-display tracking-tight", text)}>
          <span className="text-brand">Good</span>
          <span className="text-ink">Cart</span>
        </span>
      )}
    </span>
  );
}
