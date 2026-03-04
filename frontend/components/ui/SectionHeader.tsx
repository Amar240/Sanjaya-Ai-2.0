"use client";

type SectionHeaderProps = {
  title: string;
  description?: string;
  as?: "h2" | "h3" | "h4";
};

export default function SectionHeader({
  title,
  description,
  as: Tag = "h2",
}: SectionHeaderProps): JSX.Element {
  return (
    <div className="ui-section-header">
      <Tag className="ui-section-header__title">{title}</Tag>
      {description ? (
        <p className="ui-section-header__desc">{description}</p>
      ) : null}
    </div>
  );
}
