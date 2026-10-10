import { Link } from "@tanstack/react-router";

export function CareKeyLogo({ linked = true, className = "" }: { linked?: boolean; className?: string }) {
  const image = (
    <>
      <img className={`h-9 w-auto dark:hidden sm:h-10 ${className}`} src="/brand/CareKey-full-logo-light.png" alt="CareKey — Secure Emergency Health Access" />
      <img className={`hidden h-9 w-auto dark:block sm:h-10 ${className}`} src="/brand/CareKey-full-logo-dark.png" alt="CareKey — Secure Emergency Health Access" />
    </>
  );

  if (!linked) return <span className="inline-flex items-center">{image}</span>;
  return <Link to="/dashboard" aria-label="CareKey home" className="inline-flex items-center">{image}</Link>;
}
