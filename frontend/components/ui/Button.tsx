"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  children: ReactNode;
};

const variantClass: Record<ButtonVariant, string> = {
  primary: "ui-btn ui-btn--primary",
  secondary: "ui-btn ui-btn--secondary",
  ghost: "ui-btn ui-btn--ghost",
};

export default function Button({
  variant = "primary",
  className,
  children,
  ...rest
}: ButtonProps): JSX.Element {
  const cls = [variantClass[variant], className].filter(Boolean).join(" ");
  return (
    <button type="button" className={cls} {...rest}>
      {children}
    </button>
  );
}
