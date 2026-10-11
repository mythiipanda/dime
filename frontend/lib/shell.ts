export function normalizeActive(value?: string) {
  return (value ?? "").toLowerCase();
}

export function isActiveDestination(name: string, selected: string) {
  return name.toLowerCase() === selected;
}
