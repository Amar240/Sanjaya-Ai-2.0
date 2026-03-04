"use client";

type Tab = {
  id: string;
  label: string;
};

type TabsProps = {
  tabs: Tab[];
  activeId: string;
  onSelect: (id: string) => void;
  ariaLabel?: string;
};

export default function Tabs({
  tabs,
  activeId,
  onSelect,
  ariaLabel = "Tabs",
}: TabsProps): JSX.Element {
  return (
    <div className="ui-tabs" role="tablist" aria-label={ariaLabel}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={tab.id === activeId}
          className={`ui-tabs__tab ${tab.id === activeId ? "ui-tabs__tab--active" : ""}`}
          onClick={() => onSelect(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
