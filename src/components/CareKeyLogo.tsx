import { Link } from "@tanstack/react-router";

export function CareKeyLogo({ linked = true, className = "" }: { linked?: boolean; className?: string }) {
  const image = (
    <>
      <img className={`h-8 w-auto dark:hidden ${className}`} src="/brand/carekey-wordmark-light.svg" alt="CareKey" />
      <img className={`hidden h-8 w-auto dark:block ${className}`} src="/brand/carekey-wordmark-dark.svg" alt="CareKey" />
    </>
  );

  if (!linked) return <span className="inline-flex items-center">{image}</span>;
  return <Link to="/dashboard" aria-label="CareKey home" className="inline-flex items-center">{image}</Link>;
}
