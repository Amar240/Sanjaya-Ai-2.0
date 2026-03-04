"use client";

import type { ReactNode } from "react";

type AlertVariant = "error" | "warning" | "info";

type AlertProps = {
  variant?: AlertVariant;
  children: ReactNode;
};

const variantClass: Record<AlertVariant, string> = {
  error: "ui-alert ui-alert--error",
  warning: "ui-alert ui-alert--warning",
  info: "ui-alert ui-alert--info",
};

export default function Alert({
  variant = "error",
  children,
}: AlertProps): JSX.Element {
  return (
    <div className={variantClass[variant]} role="alert">
      {children}
    </div>
  );
}
