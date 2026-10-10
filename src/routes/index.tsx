import { createFileRoute, Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { CareKeyLogo } from "@/components/CareKeyLogo";
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
    <div className="min-h-screen bg-background">
      <div className="bg-warning-soft px-4 py-1.5 text-center text-xs font-medium text-warning-foreground">
        Research Prototype — Not for Clinical Use. All data is synthetic.
      </div>
      <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
       <div className="mx-auto flex max-w-6xl items-center gap-5 px-4 py-3">
        <CareKeyLogo linked={false} />
        <nav aria-label="Main navigation" className="ml-auto hidden items-center gap-5 text-sm text-muted-foreground sm:flex">
          <a href="#features" className="hover:text-foreground">Features</a>
          <Link to="/hospitals" className="hover:text-foreground">Hospitals</Link>
        </nav>
        <div className="ml-auto flex items-center gap-2 sm:ml-0">
          <ThemeToggle />
          <Button asChild size="sm"><Link to="/auth">Sign in</Link></Button>
        </div>
       </div>
      </header>

      <section className="mx-auto max-w-6xl px-4 py-16">
        <p className="mono-id text-xs uppercase text-primary">
          Emergency medical information platform
        </p>
        <h1 className="mt-4 max-w-3xl text-4xl font-semibold leading-tight tracking-tight md:text-5xl">
          The right medical information, to the right person, at the right moment.
        </h1>
        <p className="mt-5 max-w-2xl text-base text-muted-foreground">
          CareKey gives every patient an emergency medical ID and full control over who
          can see their records — with expiry, revocation and a complete audit trail.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button asChild size="lg">
            <Link to="/auth">Create a demo account</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link to="/hospitals">Find nearby hospitals</Link>
          </Button>
        </div>

        <div id="features" className="mt-16 grid gap-4 md:grid-cols-3">
          {features.map((f) => (
            <div key={f.title} className="card-surface p-6">
              <h2 className="text-base font-semibold">{f.title}</h2>
              <p className="mt-2 text-sm text-muted-foreground">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t py-8 text-center text-xs text-muted-foreground">
        CareKey — final-year research prototype. Synthetic demo data only.
      </footer>
    </div>
  );
}
