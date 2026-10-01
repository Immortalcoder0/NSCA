/** Real training endpoints only ever return a raw platform id (e.g.
 * "routeros", "mikrotik_routeros") — there is no display-name field
 * anywhere in the training API surface, so this is a purely cosmetic,
 * client-side formatting helper, not a value sourced from any endpoint. */
export function prettyPlatformName(platform: string): string {
  return platform
    .split(/[_-]+/)
    .filter(Boolean)
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ");
}
