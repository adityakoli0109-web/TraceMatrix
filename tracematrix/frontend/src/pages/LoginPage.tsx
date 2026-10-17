import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { Button, Field, Input } from "../components/ui";
import { api, setToken } from "../lib/api";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

export function LoginPage() {
  const navigate = useNavigate();
  const form = useForm({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });

  return (
    <div className="grid min-h-screen bg-white lg:grid-cols-[1.08fr_0.92fr]">
      <section className="relative hidden overflow-hidden bg-[#101b2d] px-12 py-12 text-white lg:flex lg:flex-col lg:justify-between xl:px-20">
        <div className="absolute -right-32 -top-28 h-[34rem] w-[34rem] rounded-full border border-white/[0.06]" />
        <div className="absolute -right-16 -top-12 h-[24rem] w-[24rem] rounded-full border border-white/[0.07]" />
        <div className="relative flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-[#2455d6] font-bold">TM</div>
          <span className="text-lg font-semibold tracking-tight">TraceMatrix</span>
        </div>
        <div className="relative max-w-xl">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-sky-300/20 bg-sky-300/[0.08] px-3 py-1.5 text-xs font-medium text-sky-200">
            <span className="h-1.5 w-1.5 rounded-full bg-sky-300" />
            Evidence-led blockchain investigations
          </div>
          <h1 className="text-5xl font-semibold leading-[1.08] tracking-tight xl:text-6xl">
            Follow the flow.
            <br />
            <span className="text-sky-300">Verify the story.</span>
          </h1>
          <p className="mt-6 max-w-lg text-[15px] leading-7 text-slate-300">
            Connect transaction patterns and public-source evidence in one focused analyst workspace.
          </p>
          <div className="mt-10 grid max-w-lg grid-cols-3 gap-3">
            {[
              ["01", "Map flows"],
              ["02", "Review leads"],
              ["03", "Verify evidence"],
            ].map(([number, label]) => (
              <div key={number} className="border-t border-white/15 pt-3">
                <div className="text-[11px] font-semibold tracking-[0.16em] text-sky-300">{number}</div>
                <div className="mt-1 text-xs text-slate-300">{label}</div>
              </div>
            ))}
          </div>
        </div>
        <p className="relative text-xs text-slate-500">An association is a lead to investigate—not proof of identity or wrongdoing.</p>
      </section>
      <section className="flex min-h-screen items-center justify-center px-5 py-10 sm:px-10">
        <form
          className="w-full max-w-[400px]"
          onSubmit={form.handleSubmit(async (values) => {
            try {
              const result = await api.login(values.email, values.password);
              setToken(result.access_token);
              navigate("/");
            } catch (err) {
              form.setError("password", { message: err instanceof Error ? err.message : "Login failed" });
            }
          })}
        >
          <div className="mb-9 lg:hidden">
            <div className="flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-[#2455d6] font-bold text-white">TM</div>
              <span className="text-lg font-semibold tracking-tight">TraceMatrix</span>
            </div>
          </div>
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[#2455d6]">Analyst access</div>
          <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">Welcome back</h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">Sign in to continue to your investigation workspace.</p>
          <div className="mt-8 space-y-5">
            <Field label="Work email" error={form.formState.errors.email?.message}>
              <Input className="mt-1.5 rounded-xl border-slate-200 px-3.5 py-3 text-sm shadow-sm" type="email" autoComplete="username" placeholder="analyst@organization.com" {...form.register("email")} />
            </Field>
            <Field label="Password" error={form.formState.errors.password?.message}>
              <Input className="mt-1.5 rounded-xl border-slate-200 px-3.5 py-3 text-sm shadow-sm" type="password" autoComplete="current-password" placeholder="Enter your password" {...form.register("password")} />
            </Field>
          </div>
          <Button className="mt-7 w-full rounded-xl bg-[#2455d6] py-3 text-sm font-semibold shadow-lg shadow-blue-900/15 hover:-translate-y-0.5 hover:bg-[#1947c5]" type="submit" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Signing in…" : "Sign in to workspace"}
          </Button>
          <p className="mt-6 text-center text-xs leading-5 text-slate-400">Credentials stay within this deployment. No wallet keys are requested or stored.</p>
        </form>
      </section>
    </div>
  );
}
