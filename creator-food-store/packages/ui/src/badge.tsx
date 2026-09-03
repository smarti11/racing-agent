import { cn } from "./index";
import type { HTMLAttributes } from "react";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "warning" | "info";
}

const variants = {
  default: "bg-cream text-ink border border-border",
  success: "bg-ink text-white",
  warning: "bg-cream text-ink border border-ink",
  info: "bg-cream text-muted border border-border",
};

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
        variants[variant],
        className
      )}
      {...props}
    />
  );
}
