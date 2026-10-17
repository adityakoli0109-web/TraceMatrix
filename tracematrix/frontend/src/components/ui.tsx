import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" | "ghost" }) {
  const styles = {
    primary: "bg-[#2455d6] text-white hover:bg-[#1947c5]",
    secondary: "border border-slate-200 bg-white text-slate-700 shadow-sm hover:border-slate-300 hover:bg-slate-50",
    danger: "bg-danger text-white",
    ghost: "text-[#2455d6] hover:underline",
  };
  return (
    <button
      className={`inline-flex items-center justify-center rounded-lg px-3.5 py-2 text-[13px] font-semibold disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`}
      {...props}
    />
  );
}

export function Field({ label, children, error }: { label: string; children: ReactNode; error?: string }) {
  return (
    <label className="block text-[13px]">
      <span className="mb-1 block font-semibold text-slate-700">{label}</span>
      {children}
      {error ? <span className="mt-1 block text-xs text-danger">{error}</span> : null}
    </label>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-[13px] text-slate-800 placeholder:text-slate-400 focus:border-blue-400 ${props.className ?? ""}`}
    />
  );
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={`w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-[13px] text-slate-800 focus:border-blue-400 ${props.className ?? ""}`}
    />
  );
}

export function Card({ title, children, action, className = "" }: { title?: string; children: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <section className={`overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-sm ${className}`}>
      {title ? (
        <header className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
          {action}
        </header>
      ) : null}
      <div className="p-5">{children}</div>
    </section>
  );
}

export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-10 text-center">
      <div aria-hidden="true" className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-2xl bg-blue-50 text-lg font-semibold text-[#2455d6]">↗</div>
      <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      <p className="mx-auto mt-1 max-w-lg text-[13px] leading-6 text-slate-500">{body}</p>
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "ok" | "warn" | "danger" | "accent" }) {
  const map = {
    neutral: "bg-slate-100 text-slate-600",
    ok: "bg-emerald-50 text-emerald-700",
    warn: "bg-amber-50 text-amber-700",
    danger: "bg-red-50 text-red-700",
    accent: "bg-blue-50 text-blue-700",
  };
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${map[tone]}`}>{children}</span>;
}

export function StatusPill({ status }: { status: string }) {
  const tone =
    status === "success" || status === "completed" || status === "ok"
      ? "ok"
      : status === "failed" || status === "error"
        ? "danger"
        : status === "running" || status === "active"
          ? "accent"
          : "neutral";
  return <Badge tone={tone}>{status}</Badge>;
}

export function Notice({ children }: { children: ReactNode }) {
  return <p className="rounded-xl border border-blue-100 bg-blue-50/70 px-4 py-3 text-[12px] leading-5 text-slate-600">{children}</p>;
}

export function ConfirmDialog({
  open,
  title,
  body,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  title: string;
  body: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div role="dialog" className="w-full max-w-md rounded-[3px] border border-line bg-white p-4 shadow-card">
        <h3 className="text-sm font-semibold">{title}</h3>
        <p className="mt-2 text-[13px] text-muted">{body}</p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={onConfirm}>Confirm</Button>
        </div>
      </div>
    </div>
  );
}
