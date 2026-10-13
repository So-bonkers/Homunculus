import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import * as DialogP from "@radix-ui/react-dialog";
import * as TabsP from "@radix-ui/react-tabs";
import * as TooltipP from "@radix-ui/react-tooltip";
import * as SwitchP from "@radix-ui/react-switch";
import * as SliderP from "@radix-ui/react-slider";
import * as SelectP from "@radix-ui/react-select";
import * as PopoverP from "@radix-ui/react-popover";
import * as ToggleGroupP from "@radix-ui/react-toggle-group";
import { Check, ChevronDown, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";

/* ---------------------------------------------------------------- Button */
const buttonV = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-[13px] font-medium transition-all duration-150 select-none disabled:pointer-events-none disabled:opacity-40 active:scale-[0.98] [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-accent text-white shadow-glow hover:brightness-110",
        secondary: "bg-raised text-ink border border-line-strong hover:bg-hover",
        ghost: "text-ink-2 hover:text-ink hover:bg-white/5",
        danger: "bg-bad/15 text-bad border border-bad/30 hover:bg-bad/25",
        outline: "border border-line-strong text-ink hover:bg-white/5",
        success: "bg-ok/15 text-ok border border-ok/30 hover:bg-ok/25",
      },
      size: { sm: "h-7 px-2.5 text-xs", md: "h-9 px-3.5", lg: "h-11 px-5 text-sm", icon: "size-8", "icon-sm": "size-7" },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonV> {
  loading?: boolean;
}
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, loading, children, disabled, ...p }, ref) => (
  <button ref={ref} className={cn(buttonV({ variant, size }), className)} disabled={disabled || loading} {...p}>
    {loading && <Loader2 className="animate-spin" />}
    {children}
  </button>
));
Button.displayName = "Button";

/* ---------------------------------------------------------------- Badge / status */
const badgeV = cva("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium tracking-wide", {
  variants: {
    tone: {
      neutral: "bg-white/6 text-ink-2",
      accent: "bg-accent/15 text-[#c7b8ff]",
      ok: "bg-ok/12 text-ok",
      warn: "bg-warn/12 text-warn",
      bad: "bg-bad/12 text-bad",
      cyan: "bg-cyan/12 text-cyan",
    },
  },
  defaultVariants: { tone: "neutral" },
});
export function Badge({ className, tone, ...p }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeV>) {
  return <span className={cn(badgeV({ tone }), className)} {...p} />;
}

export function Dot({ tone = "neutral", pulse }: { tone?: "neutral" | "ok" | "warn" | "bad" | "run" | "cyan"; pulse?: boolean }) {
  const c = { neutral: "bg-ink-3", ok: "bg-ok", warn: "bg-warn", bad: "bg-bad", run: "bg-run", cyan: "bg-cyan" }[tone];
  return (
    <span className="relative inline-flex size-2">
      {pulse && <span className={cn("absolute inline-flex h-full w-full animate-ping rounded-full opacity-60", c)} />}
      <span className={cn("relative inline-flex size-2 rounded-full", c)} />
    </span>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-4 animate-spin text-ink-3", className)} />;
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return <kbd className="rounded border border-line-strong bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-ink-2">{children}</kbd>;
}

/* ---------------------------------------------------------------- Panel / Section */
export function Panel({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("panel", className)} {...p} />;
}
export function SectionTitle({ children, right, className }: { children: React.ReactNode; right?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("mb-3 flex items-center justify-between gap-3", className)}>
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-3">{children}</h3>
      {right}
    </div>
  );
}
export function Empty({ icon, title, children, action }: { icon?: React.ReactNode; title: string; children?: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-line-strong px-6 py-12 text-center">
      {icon && <div className="text-ink-3 [&_svg]:size-7">{icon}</div>}
      <div className="text-sm font-medium text-ink">{title}</div>
      {children && <div className="max-w-sm text-[13px] text-ink-3">{children}</div>}
      {action}
    </div>
  );
}

/* ---------------------------------------------------------------- Inputs */
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) => (
  <input ref={ref} className={cn("h-9 w-full rounded-lg border border-line-strong bg-black/25 px-3 text-[13px] text-ink placeholder:text-ink-3 outline-none transition focus:border-accent/60 focus:bg-black/35", className)} {...p} />
));
Input.displayName = "Input";
export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...p }, ref) => (
  <textarea ref={ref} className={cn("min-h-20 w-full rounded-lg border border-line-strong bg-black/25 px-3 py-2 text-[13px] text-ink placeholder:text-ink-3 outline-none transition focus:border-accent/60 focus:bg-black/35", className)} {...p} />
));
Textarea.displayName = "Textarea";

export function Field({ label, hint, children, className }: { label: React.ReactNode; hint?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <label className={cn("flex flex-col gap-1.5", className)}>
      <span className="text-xs font-medium text-ink-2">{label}</span>
      {children}
      {hint && <span className="text-[11px] leading-snug text-ink-3">{hint}</span>}
    </label>
  );
}

export function Switch({ checked, onCheckedChange, label, hint }: { checked: boolean; onCheckedChange: (v: boolean) => void; label?: React.ReactNode; hint?: React.ReactNode }) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4">
      {(label || hint) && (
        <span className="flex flex-col gap-0.5">
          {label && <span className="text-[13px] text-ink">{label}</span>}
          {hint && <span className="text-[11px] leading-snug text-ink-3">{hint}</span>}
        </span>
      )}
      <SwitchP.Root checked={checked} onCheckedChange={onCheckedChange} className="relative mt-0.5 h-5 w-9 shrink-0 rounded-full bg-white/12 transition data-[state=checked]:bg-accent">
        <SwitchP.Thumb className="block size-4 translate-x-0.5 rounded-full bg-white shadow transition data-[state=checked]:translate-x-[18px]" />
      </SwitchP.Root>
    </label>
  );
}

export function Slider({ value, onValueChange, min = 0, max = 100, step = 1, className }: { value: number; onValueChange: (v: number) => void; min?: number; max?: number; step?: number; className?: string }) {
  return (
    <SliderP.Root value={[value]} onValueChange={(v) => onValueChange(v[0])} min={min} max={max} step={step} className={cn("relative flex h-5 w-full touch-none items-center select-none", className)}>
      <SliderP.Track className="relative h-1 grow rounded-full bg-white/10"><SliderP.Range className="absolute h-full rounded-full bg-accent" /></SliderP.Track>
      <SliderP.Thumb className="block size-3.5 rounded-full border-2 border-accent bg-white shadow outline-none" />
    </SliderP.Root>
  );
}

export interface Option { value: string; label: React.ReactNode; hint?: React.ReactNode }
export function Select({ value, onValueChange, options, className, placeholder }: { value: string; onValueChange: (v: string) => void; options: Option[]; className?: string; placeholder?: string }) {
  return (
    <SelectP.Root value={value} onValueChange={onValueChange}>
      <SelectP.Trigger className={cn("flex h-9 w-full items-center justify-between gap-2 rounded-lg border border-line-strong bg-black/25 px-3 text-[13px] text-ink outline-none focus:border-accent/60", className)}>
        <SelectP.Value placeholder={placeholder} />
        <SelectP.Icon><ChevronDown className="size-4 text-ink-3" /></SelectP.Icon>
      </SelectP.Trigger>
      <SelectP.Portal>
        <SelectP.Content position="popper" sideOffset={6} className="z-50 max-h-80 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-xl border border-line-strong bg-overlay p-1 shadow-2xl">
          <SelectP.Viewport>
            {options.map((o) => (
              <SelectP.Item key={o.value} value={o.value} className="relative flex cursor-pointer flex-col rounded-lg py-2 pr-8 pl-3 text-[13px] text-ink outline-none data-[highlighted]:bg-white/6">
                <SelectP.ItemText>{o.label}</SelectP.ItemText>
                {o.hint && <span className="text-[11px] text-ink-3">{o.hint}</span>}
                <SelectP.ItemIndicator className="absolute top-2.5 right-2.5"><Check className="size-3.5 text-accent" /></SelectP.ItemIndicator>
              </SelectP.Item>
            ))}
          </SelectP.Viewport>
        </SelectP.Content>
      </SelectP.Portal>
    </SelectP.Root>
  );
}

export function Segmented({ value, onValueChange, options, className }: { value: string; onValueChange: (v: string) => void; options: Option[]; className?: string }) {
  return (
    <ToggleGroupP.Root type="single" value={value} onValueChange={(v) => v && onValueChange(v)} className={cn("inline-flex rounded-lg border border-line-strong bg-black/25 p-0.5", className)}>
      {options.map((o) => (
        <ToggleGroupP.Item key={o.value} value={o.value} className="rounded-md px-2.5 py-1 text-xs text-ink-2 transition data-[state=on]:bg-white/10 data-[state=on]:text-ink hover:text-ink">
          {o.label}
        </ToggleGroupP.Item>
      ))}
    </ToggleGroupP.Root>
  );
}

/* ---------------------------------------------------------------- Tabs */
export const Tabs = TabsP.Root;
export function TabsList({ className, ...p }: React.ComponentProps<typeof TabsP.List>) {
  return <TabsP.List className={cn("flex items-center gap-1 border-b border-line px-1", className)} {...p} />;
}
export function TabsTrigger({ className, ...p }: React.ComponentProps<typeof TabsP.Trigger>) {
  return (
    <TabsP.Trigger
      className={cn(
        "relative flex shrink-0 items-center gap-1.5 rounded-md px-3 py-2.5 text-[13px] text-ink-3 transition hover:text-ink-2 focus-visible:bg-white/5 focus-visible:outline-none data-[state=active]:text-ink [&_svg]:size-3.5",
        "after:absolute after:inset-x-2 after:-bottom-px after:h-0.5 after:rounded-full after:bg-accent after:opacity-0 after:transition data-[state=active]:after:opacity-100",
        className,
      )}
      {...p}
    />
  );
}
export const TabsContent = TabsP.Content;

/* ---------------------------------------------------------------- Tooltip */
export const TooltipProvider = TooltipP.Provider;
export function Tip({ content, children, side = "top" }: { content: React.ReactNode; children: React.ReactElement; side?: "top" | "bottom" | "left" | "right" }) {
  if (!content) return children;
  return (
    <TooltipP.Root delayDuration={250}>
      <TooltipP.Trigger asChild>{children}</TooltipP.Trigger>
      <TooltipP.Portal>
        <TooltipP.Content side={side} sideOffset={6} className="z-50 max-w-xs rounded-lg border border-line-strong bg-overlay px-2.5 py-1.5 text-xs text-ink-2 shadow-xl">
          {content}
        </TooltipP.Content>
      </TooltipP.Portal>
    </TooltipP.Root>
  );
}

/* ---------------------------------------------------------------- Dialog */
export function Dialog({ open, onOpenChange, title, description, children, footer, wide }: {
  open: boolean; onOpenChange: (v: boolean) => void; title: React.ReactNode; description?: React.ReactNode; children?: React.ReactNode; footer?: React.ReactNode; wide?: boolean;
}) {
  return (
    <DialogP.Root open={open} onOpenChange={onOpenChange}>
      <DialogP.Portal>
        <DialogP.Overlay className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm data-[state=open]:animate-in" />
        <DialogP.Content className={cn("fixed top-1/2 left-1/2 z-50 flex max-h-[88vh] w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col panel bg-surface p-0 outline-none", wide ? "max-w-4xl" : "max-w-lg")}>
          <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
            <div>
              <DialogP.Title className="text-[15px] font-semibold text-ink">{title}</DialogP.Title>
              {description && <DialogP.Description className="mt-1 text-[13px] text-ink-3">{description}</DialogP.Description>}
            </div>
            <DialogP.Close className="rounded-md p-1 text-ink-3 hover:bg-white/5 hover:text-ink"><X className="size-4" /></DialogP.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
          {footer && <div className="flex items-center justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
        </DialogP.Content>
      </DialogP.Portal>
    </DialogP.Root>
  );
}

/* ---------------------------------------------------------------- Popover */
export const Popover = PopoverP.Root;
export const PopoverTrigger = PopoverP.Trigger;
export function PopoverContent({ className, ...p }: React.ComponentProps<typeof PopoverP.Content>) {
  return (
    <PopoverP.Portal>
      <PopoverP.Content sideOffset={8} className={cn("z-50 rounded-xl border border-line-strong bg-overlay p-3 shadow-2xl outline-none", className)} {...p} />
    </PopoverP.Portal>
  );
}

/* ---------------------------------------------------------------- Progress */
export function Progress({ value, className, tone = "accent" }: { value: number; className?: string; tone?: "accent" | "ok" | "warn" | "bad" }) {
  const c = { accent: "from-accent to-accent-2", ok: "from-ok to-emerald-300", warn: "from-warn to-amber-300", bad: "from-bad to-rose-300" }[tone];
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-white/8", className)}>
      <div className={cn("h-full rounded-full bg-gradient-to-r transition-all duration-500", c)} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}
