"use client";

import type { HTMLAttributes, ReactNode } from "react";

type CardProps = HTMLAttributes<HTMLElement> & {
  children: ReactNode;
  elevated?: boolean;
};

export default function Card({
  children,
  elevated = false,
  className,
  ...rest
}: CardProps): JSX.Element {
  const cls = ["ui-card", elevated && "ui-card--elevated", className]
    .filter(Boolean)
    .join(" ");
  return (
    <article className={cls} {...rest}>
      {children}
    </article>
  );
}
