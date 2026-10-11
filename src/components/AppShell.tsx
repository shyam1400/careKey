import { Link, useNavigate } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CareKeyLogo } from "@/components/CareKeyLogo";
import { ThemeToggle } from "@/components/ThemeToggle";

const patientNav = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/profile", label: "Medical profile" },
  { to: "/records", label: "Records" },
  { to: "/share", label: "Sharing" },
  { to: "/qr", label: "Emergency QR" },
  { to: "/history", label: "Access history" },
  { to: "/hospitals", label: "Hospitals" },
] as const;

const doctorNav = [
  { to: "/doctor", label: "My patients" },
  { to: "/emergency", label: "Emergency mode" },
  { to: "/hospitals", label: "Hospitals" },
] as const;

const adminNav = [
  { to: "/admin", label: "Admin" },
  { to: "/hospitals", label: "Hospitals" },
] as const;

const hospitalAdminNav = [
  { to: "/hospital-account", label: "Hospital dashboard" },
  { to: "/hospitals", label: "Find hospitals" },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const { profile, role, signOut } = useAuth();
  const navigate = useNavigate();
  const nav = role === "doctor" ? doctorNav : role === "admin" ? adminNav : role === "hospital_admin" ? hospitalAdminNav : patientNav;

  return (
    <div className="min-h-screen bg-background">
      <div className="bg-warning-soft px-4 py-1.5 text-center text-xs font-medium text-warning-foreground">
        Research Prototype — Not for Clinical Use. All data is synthetic.
      </div>
      <header className="sticky top-0 z-40 border-b bg-card/95 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-card/85">
        <div className="mx-auto max-w-6xl px-4">
          <div className="flex min-h-14 items-center gap-3 py-2">
            <CareKeyLogo />
            <div className="ml-auto flex items-center gap-2">
              <ThemeToggle />
              <div className="hidden text-right sm:block">
                <p className="max-w-44 truncate text-sm font-medium leading-tight">{profile?.full_name}</p>
                <Badge variant="secondary" className="mt-0.5 text-[10px] uppercase">
                  {role ?? "—"}
                </Badge>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={async () => {
                  await signOut();
                  void navigate({ to: "/auth" });
                }}
              >
                Log out
              </Button>
            </div>
          </div>
          <nav aria-label="Main navigation" className="-mx-4 flex gap-1 overflow-x-auto border-t px-4 py-1.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {nav.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="shrink-0 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                activeProps={{ className: "shrink-0 rounded-md bg-primary/10 px-3 py-2 text-sm font-semibold text-primary transition-colors" }}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}

export function PageHeading({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description ? (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}
