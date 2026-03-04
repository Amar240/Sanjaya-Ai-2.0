"use client";

type Step = {
  label: string;
};

type ProgressStepperProps = {
  steps: Step[];
  currentStep: number;
};

export default function ProgressStepper({
  steps,
  currentStep,
}: ProgressStepperProps): JSX.Element {
  return (
    <nav className="ui-stepper" aria-label="Progress">
      <ol className="ui-stepper__list">
        {steps.map((step, idx) => {
          const state =
            idx < currentStep
              ? "completed"
              : idx === currentStep
                ? "active"
                : "upcoming";
          return (
            <li
              key={step.label}
              className={`ui-stepper__item ui-stepper__item--${state}`}
              aria-current={state === "active" ? "step" : undefined}
            >
              <span className="ui-stepper__number">{idx + 1}</span>
              <span className="ui-stepper__label">{step.label}</span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
