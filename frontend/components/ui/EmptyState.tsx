"use client";

import type { ReactNode } from "react";

type EmptyStateProps = {
  title: string;
  body?: string;
  action?: ReactNode;
};

export default function EmptyState({
  title,
  body,
  action,
}: EmptyStateProps): JSX.Element {
  return (
    <div className="ui-empty">
      <h3 className="ui-empty__title">{title}</h3>
      {body ? <p className="ui-empty__body">{body}</p> : null}
      {action ? <div className="ui-empty__action">{action}</div> : null}
    </div>
  );
}
