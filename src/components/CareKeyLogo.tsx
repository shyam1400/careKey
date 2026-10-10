import { Link } from "@tanstack/react-router";

export function CareKeyLogo({ linked = true, className = "" }: { linked?: boolean; className?: string }) {
  const image = (
    <span className={className}>
      <span className="inline-flex items-center gap-2 dark:hidden">
        <img className="size-8 object-contain sm:size-9" src="/brand/CareKey-emblem-transparent.png" alt="" aria-hidden="true" />
        <span className="text-[1.35rem] font-bold tracking-tight text-foreground">Care<span className="text-primary">Key</span></span>
      </span>
      <img className="hidden h-9 w-auto max-w-36 object-contain dark:block" src="/brand/CareKey-full-logo-transparent.png" alt="CareKey — Secure Emergency Health Access" />
    </span>
  );

  if (!linked) return <span className="inline-flex items-center">{image}</span>;
  return <Link to="/dashboard" aria-label="CareKey home" className="inline-flex items-center">{image}</Link>;
}
