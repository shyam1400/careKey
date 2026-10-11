import { Link } from "@tanstack/react-router";

export function CareKeyLogo({ linked = true, className = "" }: { linked?: boolean; className?: string }) {
  const image = (
    <span className={className}>
      <img className="h-9 w-auto dark:hidden sm:h-10" src="/brand/CareKey-light-logo.png" alt="CareKey — Secure Emergency Health Access" />
      <img className="hidden h-9 w-auto max-w-36 object-contain dark:block" src="/brand/CareKey-full-logo-transparent.png" alt="CareKey — Secure Emergency Health Access" />
    </span>
  );

  if (!linked) return <span className="inline-flex items-center">{image}</span>;
  return <Link to="/dashboard" aria-label="CareKey home" className="inline-flex items-center">{image}</Link>;
}
