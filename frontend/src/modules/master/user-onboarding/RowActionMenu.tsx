import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import shared from "@/modules/master/shared/NameMasterPage.module.css";
import { MENU_WIDTH, type RowMenuAnchor } from "./rowMenuAnchor";

export type RowMenuItem = {
  key: string;
  label: string;
  danger?: boolean;
  disabled?: boolean;
  onSelect: () => void;
};

export function RowActionMenu({
  anchor,
  items,
  onClose,
}: {
  anchor: RowMenuAnchor;
  items: RowMenuItem[];
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onPointerDown(event: PointerEvent) {
      const target = event.target as HTMLElement;
      if (ref.current?.contains(target)) return;
      if (target.closest?.("[data-action-trigger='true']")) return;
      onClose();
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("scroll", onClose, true);
    window.addEventListener("resize", onClose);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("scroll", onClose, true);
      window.removeEventListener("resize", onClose);
    };
  }, [onClose]);

  return createPortal(
    <div
      ref={ref}
      className={shared.actionsMenu}
      role="menu"
      style={{ top: anchor.top, left: anchor.left, minWidth: MENU_WIDTH }}
    >
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          role="menuitem"
          className={`${shared.menuItem} ${item.danger ? shared.menuItemDanger : ""}`}
          disabled={item.disabled}
          onClick={() => {
            onClose();
            item.onSelect();
          }}
        >
          {item.label}
        </button>
      ))}
    </div>,
    document.body,
  );
}
