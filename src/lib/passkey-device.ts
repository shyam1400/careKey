export function passkeyDeviceMode(): "phone" | "computer" {
  return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent) ? "phone" : "computer";
}

export function patientPasskeyOptionsPath(path: string): string {
  return `${path}?device=${passkeyDeviceMode()}`;
}
