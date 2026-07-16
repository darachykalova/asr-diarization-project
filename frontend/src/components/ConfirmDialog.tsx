import { useEffect, useRef, useState } from "react";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const FOCUSABLE_SELECTOR =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

export function ConfirmDialog({
  open, title, message, confirmLabel = "Подтвердить", danger, onConfirm, onCancel,
}: ConfirmDialogProps) {
  const [visible, setVisible] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<Element | null>(null);

  useEffect(() => {
    if (!open) {
      setVisible(false);
      if (triggerRef.current instanceof HTMLElement) {
        triggerRef.current.focus();
      }
      return;
    }
    triggerRef.current = document.activeElement;
    const id = requestAnimationFrame(() => {
      setVisible(true);
      cancelRef.current?.focus();
    });
    return () => cancelAnimationFrame(id);
  }, [open]);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      e.stopPropagation();
      onCancel();
      return;
    }
    if (e.key !== "Tab" || !dialogRef.current) return;
    const focusable = Array.from(
      dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  if (!open) return null;
  return (
    <div
      className={`fixed inset-0 bg-black/40 flex items-center justify-center z-50 transition-opacity duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] ${
        visible ? "opacity-100" : "opacity-0"
      }`}
      onClick={onCancel}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        onKeyDown={handleKeyDown}
        className={`bg-white rounded-lg shadow-xl p-6 max-w-sm w-full mx-4 transition-[opacity,transform] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:scale-100 ${
          visible ? "opacity-100 scale-100" : "opacity-0 scale-[0.97]"
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="confirm-dialog-title" className="text-lg font-semibold text-gray-800 mb-2">{title}</h3>
        <p className="text-sm text-gray-600 mb-6">{message}</p>
        <div className="flex justify-end gap-3">
          <button
            ref={cancelRef}
            onClick={onCancel}
            className="px-4 py-2 rounded text-sm text-gray-600 border border-gray-300 hover:bg-gray-50 active:scale-[0.97] transition-[background-color,transform] motion-reduce:active:scale-100"
          >
            Отмена
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 rounded text-sm text-white active:scale-[0.97] transition-[background-color,transform] motion-reduce:active:scale-100 ${
              danger ? "bg-red-600 hover:bg-red-700" : "bg-blue-600 hover:bg-blue-700"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
