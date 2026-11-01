import { forwardRef, useId } from "react";
import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes, ReactNode } from "react";
import { cn } from "./cn";

const CONTROL =
  "w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink " +
  "placeholder:text-muted transition-colors focus:border-accent " +
  "disabled:opacity-60 aria-[invalid=true]:border-danger";

/** Label + control + error wrapper. Wire `error` from react-hook-form. */
export function Field({
  label,
  error,
  hint,
  required,
  children,
  htmlFor,
  descriptionId,
}: {
  label: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
  htmlFor?: string;
  descriptionId?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-ink">
        {label}
        {required && <span className="text-danger ml-0.5">*</span>}
      </label>
      {children}
      {hint && !error && <p id={descriptionId} className="text-xs text-muted">{hint}</p>}
      {error && (
        <p id={descriptionId} className="text-xs text-danger" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} className={cn(CONTROL, className)} {...props} />;
  },
);

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...props }, ref) {
    return <textarea ref={ref} className={cn(CONTROL, "min-h-24 resize-y", className)} {...props} />;
  },
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, ...props }, ref) {
    return <select ref={ref} className={cn(CONTROL, "appearance-none pr-8", className)} {...props} />;
  },
);

/** Convenience: a labelled text input in one call (uncontrolled or RHF-registered). */
export const TextField = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string; hint?: string }
>(function TextField({ label, error, hint, required, id, ...props }, ref) {
  const generated = useId();
  const fieldId = id || generated;
  const descriptionId = error || hint ? `${fieldId}-description` : undefined;
  return (
    <Field label={label} error={error} hint={hint} required={required} htmlFor={fieldId} descriptionId={descriptionId}>
      <Input id={fieldId} ref={ref} aria-invalid={!!error} required={required} {...props}
        aria-describedby={[props["aria-describedby"], descriptionId].filter(Boolean).join(" ") || undefined} />
    </Field>
  );
});
