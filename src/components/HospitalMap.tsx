import { MapContainer, TileLayer, Marker, Popup, CircleMarker, useMap } from "react-leaflet";
import { useEffect } from "react";
import L from "leaflet";

export type MapHospital = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  distance: number;
};

function hospitalIcon(selected: boolean) {
  const background = selected ? "#075985" : "#0e7490";
  return L.divIcon({
    className: "",
    html: `<div style="width:34px;height:34px;border:3px solid white;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:${background};box-shadow:0 2px 6px #0005;display:grid;place-items:center"><span style="color:white;font:700 20px/1 Arial;transform:rotate(45deg)">+</span></div>`,
    iconSize: [34, 34],
    iconAnchor: [17, 34],
    popupAnchor: [0, -32],
  });
}

export default function HospitalMap({
  center,
  userLocation,
  hospitals,
  selectedHospitalId,
  onSelect,
}: {
  center: { lat: number; lon: number };
  userLocation: { lat: number; lon: number } | null;
  hospitals: MapHospital[];
  selectedHospitalId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <MapContainer
      center={[center.lat, center.lon]}
      zoom={12}
      className="relative z-0 isolate h-[420px] w-full rounded-lg border"
      scrollWheelZoom
    >
      <MapViewport center={center} userLocation={userLocation} hospitals={hospitals} selectedHospitalId={selectedHospitalId} />
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <CircleMarker center={[center.lat, center.lon]} radius={9} pathOptions={{ weight: 3 }}>
        <Popup>You are here (approximate)</Popup>
      </CircleMarker>
      {hospitals.map((h) => (
        <Marker
          key={h.id}
          position={[h.latitude, h.longitude]}
          icon={hospitalIcon(h.id === selectedHospitalId)}
          eventHandlers={{ click: () => onSelect(h.id) }}
        >
          <Popup>
            <strong>{h.name}</strong>
            <br />
            {h.distance.toFixed(1)} km away in a straight line
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}

function MapViewport({
  center,
  userLocation,
  hospitals,
  selectedHospitalId,
}: {
  center: { lat: number; lon: number };
  userLocation: { lat: number; lon: number } | null;
  hospitals: MapHospital[];
  selectedHospitalId: string | null;
}) {
  const map = useMap();

  useEffect(() => {
    const selected = hospitals.find((hospital) => hospital.id === selectedHospitalId);
    if (selected) {
      map.flyTo([selected.latitude, selected.longitude], Math.max(map.getZoom(), 14), { duration: 0.45 });
      return;
    }

    const points: L.LatLngExpression[] = hospitals.map((hospital) => [hospital.latitude, hospital.longitude]);
    if (userLocation) points.push([userLocation.lat, userLocation.lon]);
    if (points.length > 1) {
      map.fitBounds(L.latLngBounds(points), { padding: [32, 32], maxZoom: 14 });
    } else if (points.length === 1) {
      map.setView(points[0], 13);
    } else {
      map.setView([center.lat, center.lon], 12);
    }
  }, [map, center.lat, center.lon, userLocation, hospitals, selectedHospitalId]);

  return null;
}
