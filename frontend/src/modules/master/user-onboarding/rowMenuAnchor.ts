export type RowMenuAnchor = { id: number; top: number; left: number };

export const MENU_WIDTH = 188;
const ITEM_HEIGHT = 36;

/** Positions a fixed menu next to the trigger button, flipping upwards near the viewport edge. */
export function anchorFor(id: number, button: HTMLElement, itemCount: number): RowMenuAnchor {
  const rect = button.getBoundingClientRect();
  const height = itemCount * ITEM_HEIGHT + 12;
  const left = Math.min(Math.max(8, rect.right - MENU_WIDTH), window.innerWidth - MENU_WIDTH - 8);
  const openUp = rect.bottom + 6 + height > window.innerHeight;
  const top = openUp ? Math.max(8, rect.top - height - 6) : rect.bottom + 6;
  return { id, top, left };
}
