"use client";

import type { HTMLAttributes, ReactNode } from "react";

type ChipVariant = "default" | "success" | "warning" | "error" | "muted";

type ChipProps = HTMLAttributes<HTMLSpanElement> & {
  variant?: ChipVariant;
  children: ReactNode;
};

const variantClass: Record<ChipVariant, string> = {
  default: "ui-chip",
  success: "ui-chip ui-chip--success",
  warning: "ui-chip ui-chip--warning",
  error: "ui-chip ui-chip--error",
  muted: "ui-chip ui-chip--muted",
};

export default function Chip({
  variant = "default",
  className,
  children,
  ...rest
}: ChipProps): JSX.Element {
  const cls = [variantClass[variant], className].filter(Boolean).join(" ");
  return (
    <span className={cls} {...rest}>
      {children}
    </span>
  );
}
