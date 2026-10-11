import { createFileRoute, Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ThemeToggle";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "CareKey — Emergency medical ID and consent-based sharing" },
      {
        name: "description",
        content:
          "Research prototype: emergency medical ID with QR, identity verification and patient-controlled sharing of medical records with doctors.",
      },
      { property: "og:title", content: "CareKey — Emergency medical ID" },
      {
        property: "og:description",
        content:
          "Emergency medical profiles, consent-based record sharing and a nearby hospital finder. Research prototype with synthetic data.",
      },
    ],
  }),
  component: Landing,
});

const features = [
  {
    title: "Emergency mode",
    body: "Identify a patient by QR or Medical ID, verify identity, and see only critical information. Every access is logged.",
  },
  {
    title: "Patient-controlled sharing",
    body: "Patients choose exactly which categories a doctor can see, for how long, and can revoke access at any time.",
  },
  {
    title: "Nearby hospitals",
    body: "Find emergency-capable hospitals near your location on an open map, sorted by real distance.",
  },
];

function Landing() {
  return (
    <div className="relative min-h-screen bg-background">
      <div className="bg-warning-soft px-4 py-1.5 text-center text-xs font-medium text-warning-foreground">
        Research Prototype — Not for Clinical Use. All data is synthetic.
      </div>
      <div className="absolute right-4 top-12 z-10"><ThemeToggle /></div>

      <main className="mx-auto max-w-6xl px-4 pb-12 pt-16 sm:pt-20">
        <section className="mx-auto max-w-4xl text-center">
          <div className="mx-auto mb-7 w-full max-w-[52rem]">
            <img className="block h-auto w-full dark:hidden" src="/brand/CareKey-light-logo.png" alt="CareKey — Secure Emergency Health Access" />
            <img className="hidden h-auto w-full dark:block" src="/brand/CareKey-full-logo-transparent.png" alt="CareKey — Secure Emergency Health Access" />
          </div>
          <h1 className="mx-auto max-w-3xl text-3xl font-semibold leading-tight tracking-tight sm:text-4xl md:text-5xl">
            The right medical information, to the right person, at the right moment.
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-base text-muted-foreground sm:text-lg">
            CareKey gives every patient an emergency medical ID and control over who can see their records, with expiry, revocation and a complete audit trail.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Button asChild size="lg">
            <Link to="/auth">Create a demo account</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link to="/hospitals">Find nearby hospitals</Link>
          </Button>
          </div>
        </section>

        <section id="features" className="mt-16">
          <div className="mb-6 text-center">
            <p className="mono-id text-xs uppercase text-primary">Built around patient choice</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight">Care, connected securely</h2>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
          {features.map((f) => (
            <div key={f.title} className="card-surface p-6 text-left transition duration-200 hover:-translate-y-0.5 hover:shadow-md">
              <h2 className="text-base font-semibold">{f.title}</h2>
              <p className="mt-2 text-sm text-muted-foreground">{f.body}</p>
            </div>
          ))}
          </div>
        </section>
        <div className="mt-8 text-center">
          <Link to="/auth" className="text-sm font-medium text-primary hover:underline">Already have an account? Sign in</Link>
        </div>
      </main>

      <footer className="border-t py-8 text-center text-xs text-muted-foreground">
        CareKey — final-year research prototype. Synthetic demo data only.
      </footer>
    </div>
  );
}
