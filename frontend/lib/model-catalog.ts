import type { ModelOption } from "./chat";

export function modelLabel(id: string): string {
  const slug = id.split(":").slice(1).join(":") || id;
  return slug.split("/").pop()!.replace(/:free$/, "").replace(/-\d{4,}$/, "").split("-")
    .map((word) => /^\d+(?:\.\d+)?b$/i.test(word) ? word.toUpperCase() : word.charAt(0).toUpperCase() + word.slice(1)).join(" ");
}

export function availableModel(models: ModelOption[], selected: string | null): string | null {
  const usable = models.filter((model) => model.available !== false);
  return usable.find((model) => model.id === selected)?.id || usable.find((model) => model.default)?.id || usable[0]?.id || null;
}
