import { createFileRoute, ClientOnly, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useMemo, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { AppShell, PageHeading } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { haversineKm } from "@/lib/carekey";
import { CareKeyLogo } from "@/components/CareKeyLogo";
import { ThemeToggle } from "@/components/ThemeToggle";

const HospitalMap = lazy(() => import("@/components/HospitalMap"));

export const Route = createFileRoute("/hospitals")({
  head: () => ({
    meta: [
      { title: "Find nearby hospitals — CareKey" },
      {
        name: "description",
        content:
          "Find emergency, trauma and ambulance-equipped hospitals near you on an OpenStreetMap map, sorted by distance.",
      },
      { property: "og:title", content: "Find nearby hospitals — CareKey" },
      {
        property: "og:description",
        content: "Nearby emergency hospitals sorted by distance with directions.",
      },
    ],
  }),
  component: HospitalsRoute,
});

const DEFAULT = { lat: 12.9716, lon: 77.5946 };

function HospitalsRoute() {
  const { session } = useAuth();
  const body = <HospitalsPage />;
  if (session) return <AppShell>{body}</AppShell>;
  return (
    <div className="min-h-screen bg-background">
      <div className="bg-warning-soft px-4 py-1.5 text-center text-xs font-medium text-warning-foreground">
        Research Prototype — Not for Clinical Use. Demo hospital data.
      </div>
      <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3">
          <CareKeyLogo linked={false} />
          <Link to="/" className="ml-auto text-sm text-muted-foreground hover:underline">Home</Link>
          <ThemeToggle />
        </div>
      </header>
      <div className="mx-auto max-w-6xl px-4 py-6">
        {body}
      </div>
    </div>
  );
}

const FILTERS = [
  { key: "emergency", label: "Emergency department" },
  { key: "trauma", label: "Trauma care" },
  { key: "ambulance", label: "Ambulance" },
  { key: "open_24h", label: "Open now" },
] as const;

type FilterKey = (typeof FILTERS)[number]["key"];

function HospitalsPage() {
  const [loc, setLoc] = useState<{ lat: number; lon: number } | null>(null);
  const [locAccuracy, setLocAccuracy] = useState<number | null>(null);
  const [locStatus, setLocStatus] = useState<"idle" | "asking" | "granted" | "denied">("idle");
  const [locError, setLocError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterKey[]>([]);
  const [selected, setSelected] = useState<string | null>(null);

  const { data: hospitals = [], isLoading, error, refetch } = useQuery({
    queryKey: ["hospitals"],
    staleTime: 60_000,
    queryFn: async () => {
      const response = await fetch(`${import.meta.env.VITE_CAREKEY_API_URL || "http://localhost:8000"}/hospitals`);
      if (!response.ok) throw new Error("Could not load hospitals from the CareKey API.");
      return (await response.json()) as Array<{
        id: string;
        name: string;
        latitude: number;
        longitude: number;
        address: string | null;
        phone: string | null;
        emergency: boolean;
        trauma: boolean;
        ambulance: boolean;
        open_24h: boolean;
      }>;
    },
  });

  function locate() {
    if (!("geolocation" in navigator)) {
      setLoc(null);
      setLocAccuracy(null);
      setLocStatus("denied");
      setLocError("This browser does not support location. Showing distances from the demo city centre.");
      return;
    }
    setLocStatus("asking");
    setLocError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude, accuracy } = pos.coords;
        if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180) {
          setLoc(null);
          setLocAccuracy(null);
          setLocStatus("denied");
          setLocError("Your device returned invalid coordinates. Showing distances from the demo city centre.");
          return;
        }
        setLoc({ lat: latitude, lon: longitude });
        setLocAccuracy(Number.isFinite(accuracy) && accuracy > 0 ? accuracy : null);
        setLocStatus("granted");
      },
      (error) => {
        setLoc(null);
        setLocAccuracy(null);
        setLocStatus("denied");
        setLocError(error.code === error.PERMISSION_DENIED
          ? "Location permission was denied. Allow location access for this site in your browser settings, then retry. Showing distances from the demo city centre."
          : error.code === error.TIMEOUT
            ? "Your device took too long to provide a location. Check that device location services are on, then retry. Showing distances from the demo city centre."
            : "Your device could not determine a location. Check that device location services are on, then retry. Showing distances from the demo city centre.");
      },
      { enableHighAccuracy: true, timeout: 25000, maximumAge: 0 },
    );
  }

  const origin = loc ?? DEFAULT;
  const list = useMemo(
    () =>
      hospitals
        .map((h) => ({
          ...h,
          distance: haversineKm(origin, { lat: h.latitude, lon: h.longitude }),
        }))
        .filter((h) => filters.every((f) => h[f]))
        .sort((a, b) => a.distance - b.distance),
    [hospitals, origin, filters],
  );
  const current = list.find((h) => h.id === selected) ?? null;

  const directionsUrl = (h: { latitude: number; longitude: number }) =>
    `https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route=${origin.lat}%2C${origin.lon}%3B${h.latitude}%2C${h.longitude}`;

  return (
    <>
      <PageHeading
        title="Find nearby hospitals"
        description="Distances are straight-line estimates. Open directions for a road route."
        action={
          <Button onClick={locate} disabled={locStatus === "asking"}>
            {locStatus === "asking" ? "Locating…" : loc ? "Update my location" : "Use my location"}
          </Button>
        }
      />
      {locStatus === "denied" ? (
        <p className="mb-4 rounded-md bg-warning-soft p-3 text-sm text-warning-foreground">
          {locError}
        </p>
      ) : null}
      {locStatus === "granted" && locAccuracy !== null ? (
        <p className={`mb-4 rounded-md p-3 text-sm ${locAccuracy > 1500 ? "bg-warning-soft text-warning-foreground" : "bg-success-soft"}`}>
          {locAccuracy > 1500
            ? `Your device provided a rough location (about ±${(locAccuracy / 1000).toFixed(1)} km). Turn on precise location in device settings and retry for a better result.`
            : `Using your device location (about ±${Math.max(1, Math.round(locAccuracy))} m).`}
        </p>
      ) : null}
      {locStatus === "idle" ? (
        <p className="mb-4 rounded-md bg-info-soft p-3 text-sm">
          Tap “Use my location” to sort by distance from you. Until then, distances are from the demo
          city centre.
        </p>
      ) : null}
      {error ? (
        <div role="alert" className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <span>Could not load the hospital directory. Check your connection and retry.</span>
          <Button size="sm" variant="outline" onClick={() => void refetch()}>Retry</Button>
        </div>
      ) : null}

      <div className="mb-4 flex flex-wrap gap-4">
        {FILTERS.map((f) => (
          <label key={f.key} className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={filters.includes(f.key)}
              onCheckedChange={(v) =>
                setFilters(v ? [...filters, f.key] : filters.filter((x) => x !== f.key))
              }
            />
            {f.label}
          </label>
        ))}
      </div>

      <ClientOnly fallback={<div className="h-[420px] animate-pulse rounded-lg bg-muted" />}>
        <Suspense fallback={<div className="h-[420px] animate-pulse rounded-lg bg-muted" />}>
          <HospitalMap center={origin} userLocation={loc} hospitals={list} selectedHospitalId={selected} onSelect={setSelected} />
        </Suspense>
      </ClientOnly>

      {isLoading ? <p className="mt-4 text-sm text-muted-foreground">Loading hospital directory…</p> : null}
      {!isLoading && !error && list.length === 0 ? (
        <div className="mt-4 rounded-lg border border-dashed p-5 text-sm text-muted-foreground">
          No hospitals match these filters yet. An administrator can add fictional demo entries from the Admin page.
        </div>
      ) : null}
      <p className="mt-6 mb-3 text-sm text-muted-foreground">{list.length} hospitals found · distances are approximate straight-line estimates</p>
      <div className="grid gap-4 md:grid-cols-2">
        {list.map((h) => (
          <div key={h.id} className="card-surface p-5">
            <div className="flex items-start justify-between gap-3">
              <h3 className="font-semibold">{h.name}</h3>
              <span className="mono-id whitespace-nowrap text-sm font-semibold text-primary">
                {h.distance.toFixed(1)} km
              </span>
            </div>
            <dl className="mt-3 grid grid-cols-3 gap-2 text-xs">
              <Capability label="Emergency" ok={h.emergency} />
              <Capability label="Trauma" ok={h.trauma} />
              <Capability label="Ambulance" ok={h.ambulance} />
            </dl>
            <div className="mt-4 flex gap-2">
              <Button size="sm" variant="outline" onClick={() => setSelected(h.id)}>
                View details
              </Button>
              <Button size="sm" asChild>
                <a href={directionsUrl(h)} target="_blank" rel="noopener noreferrer">
                  Open road directions
                </a>
              </Button>
            </div>
          </div>
        ))}
      </div>

      <Dialog open={!!current} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent>
          {current ? (
            <>
              <DialogHeader>
                <DialogTitle>{current.name}</DialogTitle>
                <DialogDescription>{current.distance.toFixed(1)} km away</DialogDescription>
              </DialogHeader>
              <div className="space-y-2 text-sm">
                <p>
                    <strong>Address:</strong> {current.address || "Not provided"}
                </p>
                <p>
                  <strong>Phone:</strong>{" "}
                  {current.phone ? (
                    <a className="text-primary underline" href={`tel:${current.phone}`}>{current.phone}</a>
                  ) : "Not provided"}
                </p>
                <p>
                  <strong>Status:</strong> {current.open_24h ? "Open 24 hours" : "Limited hours"}
                </p>
                <div className="grid grid-cols-3 gap-2 pt-2 text-xs">
                  <Capability label="Emergency" ok={current.emergency} />
                  <Capability label="Trauma" ok={current.trauma} />
                  <Capability label="Ambulance" ok={current.ambulance} />
                </div>
              </div>
              <Button asChild className="mt-2">
                <a href={directionsUrl(current)} target="_blank" rel="noopener noreferrer">
                  Open road directions
                </a>
              </Button>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}

function Capability({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className={`rounded-md px-2 py-1.5 ${ok ? "bg-success-soft" : "bg-muted text-muted-foreground"}`}>
      <dt className="font-medium">{label}</dt>
      <dd>{ok ? "Available" : "Not available"}</dd>
    </div>
  );
}
