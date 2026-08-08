/**
 * The small set of building blocks the shell needs.
 *
 * Deliberately plain: no charts, no trading widgets, no form that submits an
 * action. Sprint 063 is a foundation, and a component library grown ahead of
 * the screens that use it is a library nobody has checked against real needs.
 */

import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from "react";

function join(...values: (string | false | undefined)[]): string {
  return values.filter(Boolean).join(" ");
}

export type ButtonVariant = "primary" | "secondary" | "quiet";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly variant?: ButtonVariant;
}

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary: "bg-sky-600 text-white hover:bg-sky-500 disabled:bg-sky-900",
  secondary: "bg-panel text-slate-100 border border-edge hover:border-slate-500",
  quiet: "text-muted hover:text-slate-100",
};

export function Button({ variant = "primary", className, ...props }: ButtonProps) {
  return (
    <button
      {...props}
      className={join(
        "rounded px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
        BUTTON_STYLES[variant],
        className,
      )}
    />
  );
}

export interface FieldProps {
  readonly label: string;
  readonly htmlFor: string;
  readonly hint?: string;
  readonly children: ReactNode;
}

export function Field({ label, htmlFor, hint, children }: FieldProps) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={htmlFor} className="text-sm text-slate-200">
        {label}
      </label>
      {children}
      {hint ? <p className="text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={join(
        "rounded border border-edge bg-panel px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500",
        className,
      )}
    />
  );
}

export function Select({
  className,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={join(
        "rounded border border-edge bg-panel px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500",
        className,
      )}
    >
      {children}
    </select>
  );
}

export function Card({
  title,
  children,
}: {
  readonly title?: string;
  readonly children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-edge bg-panel p-4">
      {title ? <h2 className="mb-3 text-sm font-semibold text-slate-200">{title}</h2> : null}
      {children}
    </section>
  );
}

export function PageHeader({
  title,
  description,
}: {
  readonly title: string;
  readonly description?: string;
}) {
  return (
    <header className="mb-6">
      <h1 className="text-xl font-semibold text-slate-100">{title}</h1>
      {description ? <p className="mt-1 text-sm text-muted">{description}</p> : null}
    </header>
  );
}

export type BadgeTone = "neutral" | "good" | "warn" | "bad";

const BADGE_STYLES: Record<BadgeTone, string> = {
  neutral: "bg-slate-800 text-slate-200",
  good: "bg-emerald-900 text-emerald-200",
  warn: "bg-amber-900 text-amber-100",
  bad: "bg-rose-900 text-rose-100",
};

export function Badge({
  tone = "neutral",
  children,
}: {
  readonly tone?: BadgeTone;
  readonly children: ReactNode;
}) {
  return (
    <span className={join("rounded px-2 py-0.5 text-xs", BADGE_STYLES[tone])}>
      {children}
    </span>
  );
}

/** A table shell. Columns and rows arrive with the screens that need them. */
export function TableShell({
  columns,
  children,
}: {
  readonly columns: readonly string[];
  readonly children?: ReactNode;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-edge text-xs uppercase text-muted">
            {columns.map((column) => (
              <th key={column} scope="col" className="px-3 py-2 font-medium">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
