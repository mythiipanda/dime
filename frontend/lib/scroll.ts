type Box = Pick<Element, "scrollHeight" | "clientHeight" | "scrollTop" | "scrollTo">;

export function shouldFollow(atBottom: boolean, running: boolean): boolean {
  return atBottom && running;
}

export function isAtBottom(box: Pick<Box, "scrollHeight" | "clientHeight" | "scrollTop">): boolean {
  return box.scrollHeight - (box.scrollTop + box.clientHeight) < 120;
}

export function scrolledUp(prevTop: number, nextTop: number): boolean {
  return nextTop + 4 < prevTop;
}

export function findScroller(from: { parentElement?: unknown } | null): Element | null {
  let el: unknown = from?.parentElement ?? null;
  while (el && typeof el === "object") {
    const candidate = el as Element & {
      scrollHeight?: unknown;
      clientHeight?: unknown;
    };
    if (
      typeof candidate.scrollHeight === "number" &&
      typeof candidate.clientHeight === "number" &&
      candidate.scrollHeight > candidate.clientHeight + 4
    ) {
      return candidate;
    }
    el = (candidate as { parentElement?: unknown }).parentElement ?? null;
  }
  return null;
}

export function glideToBottom(box: Box | null): boolean {
  if (!box || typeof box.scrollTo !== "function") return false;
  try {
    box.scrollTo({ top: box.scrollHeight, behavior: "smooth" });
    return true;
  } catch {
    return false;
  }
}

export function jumpToTop(box: Box | null): boolean {
  if (!box || typeof box.scrollTo !== "function") return false;
  try {
    box.scrollTo(0, 0);
    return true;
  } catch {
    return false;
  }
}
