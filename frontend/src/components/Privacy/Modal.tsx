import { useRef, type ReactNode } from 'react';
import { Dialog } from '@base-ui/react/dialog';
import { AlertDialog } from '@base-ui/react/alert-dialog';
import { X } from 'lucide-react';

/**
 * Modal dialogs in the Falkyria palette, built on Base UI: focus is trapped
 * inside, Esc closes (the caller decides what closing means) and the title
 * and description label the dialog for screen readers.
 */

const BACKDROP_CLASS =
  'fixed inset-0 z-[70] transition-opacity duration-150 ' +
  'data-[starting-style]:opacity-0 data-[ending-style]:opacity-0 motion-reduce:transition-none';

const POPUP_CLASS =
  'fixed left-1/2 top-1/2 z-[70] flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] ' +
  '-translate-x-1/2 -translate-y-1/2 flex-col rounded-xl outline-none ' +
  'transition-[opacity,transform] duration-150 data-[starting-style]:opacity-0 ' +
  'data-[starting-style]:scale-[0.97] data-[ending-style]:opacity-0 motion-reduce:transition-none';

// The page dims to half under any dialog (warm black, matching the palette).
const BACKDROP_STYLE = { background: 'rgba(8, 8, 7, 0.5)' } as const;

const POPUP_STYLE = {
  background: 'var(--color-surface)',
  color: 'var(--color-text)',
  border: '1px solid var(--color-border)',
  boxShadow: 'var(--shadow-lg)',
} as const;

const WIDTHS = { sm: 'sm:max-w-md', md: 'sm:max-w-xl', lg: 'sm:max-w-2xl' } as const;

export type ModalChangeDetails = Dialog.Root.ChangeEventDetails;

interface ModalProps {
  open: boolean;
  /** Called when the user asks to close (Esc, close button). */
  onOpenChange: (open: boolean, details: ModalChangeDetails) => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  /** Optional element shown left of the title (e.g. the mascot). */
  icon?: ReactNode;
  size?: keyof typeof WIDTHS;
  /** Show the X button in the corner (off for choices that need an answer). */
  showClose?: boolean;
  /** Ignore clicks on the backdrop (on for choices that need an answer). */
  disablePointerDismissal?: boolean;
  /** Focus the dialog itself on open instead of its first control (no preselected answer). */
  focusDialog?: boolean;
}

export function Modal({
  open,
  onOpenChange,
  title,
  children,
  footer,
  icon,
  size = 'md',
  showClose = true,
  disablePointerDismissal = false,
  focusDialog = false,
}: ModalProps) {
  const popupRef = useRef<HTMLDivElement>(null);
  return (
    <Dialog.Root
      open={open}
      onOpenChange={onOpenChange}
      disablePointerDismissal={disablePointerDismissal}
    >
      <Dialog.Portal>
        <Dialog.Backdrop className={BACKDROP_CLASS} style={BACKDROP_STYLE} />
        <Dialog.Popup
          ref={popupRef}
          initialFocus={focusDialog ? popupRef : undefined}
          className={`${POPUP_CLASS} ${WIDTHS[size]}`}
          style={POPUP_STYLE}
        >
          <div className="flex items-center gap-3 px-5 pt-5 pb-3 pr-12 relative">
            {icon}
            <Dialog.Title className="text-base font-semibold leading-snug">{title}</Dialog.Title>
            {showClose && (
              <Dialog.Close
                aria-label="Fechar"
                className="absolute right-3 top-3 p-1.5 rounded-lg cursor-pointer transition-colors hover:bg-[var(--color-bg-tertiary)] focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                <X size={16} aria-hidden="true" />
              </Dialog.Close>
            )}
          </div>
          <Dialog.Description
            render={<div />}
            className="min-h-0 flex-1 overflow-y-auto px-5 pb-4"
          >
            {children}
          </Dialog.Description>
          {footer && (
            <div
              className="flex flex-col-reverse gap-2 px-5 py-4 sm:flex-row sm:justify-end"
              style={{ borderTop: '1px solid var(--color-border)' }}
            >
              {footer}
            </div>
          )}
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

interface ConfirmModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  onConfirm: () => void;
  busy?: boolean;
  /** Paint the confirm button as a destructive action. */
  destructive?: boolean;
}

/** A yes/no question (role="alertdialog"). Focus starts on "Cancelar". */
export function ConfirmModal({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  cancelLabel = 'Cancelar',
  onConfirm,
  busy = false,
  destructive = false,
}: ConfirmModalProps) {
  return (
    <AlertDialog.Root open={open} onOpenChange={(next) => onOpenChange(next)}>
      <AlertDialog.Portal>
        <AlertDialog.Backdrop className={BACKDROP_CLASS} style={BACKDROP_STYLE} />
        <AlertDialog.Popup className={`${POPUP_CLASS} ${WIDTHS.sm}`} style={POPUP_STYLE}>
          <div className="px-5 pt-5 pb-4">
            <AlertDialog.Title className="text-base font-semibold leading-snug mb-2">
              {title}
            </AlertDialog.Title>
            <AlertDialog.Description
              render={<div />}
              className="text-sm leading-relaxed"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              {description}
            </AlertDialog.Description>
          </div>
          <div
            className="flex flex-col-reverse gap-2 px-5 py-4 sm:flex-row sm:justify-end"
            style={{ borderTop: '1px solid var(--color-border)' }}
          >
            <AlertDialog.Close className={buttonClass()} style={buttonStyle('neutral')} disabled={busy}>
              {cancelLabel}
            </AlertDialog.Close>
            <button
              type="button"
              onClick={onConfirm}
              disabled={busy}
              aria-busy={busy || undefined}
              className={buttonClass()}
              style={buttonStyle(destructive ? 'danger' : 'primary')}
            >
              {confirmLabel}
            </button>
          </div>
        </AlertDialog.Popup>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}

export type ButtonTone = 'neutral' | 'primary' | 'danger';

/** Shared button shape for dialogs and the privacy section (colors: buttonStyle). */
export function buttonClass(size: 'md' | 'sm' = 'md'): string {
  const metrics = size === 'sm' ? 'min-h-8 px-3 py-1.5 text-xs' : 'min-h-9 px-4 py-2 text-sm';
  return (
    `inline-flex items-center justify-center gap-1.5 ${metrics} rounded-lg font-medium ` +
    'cursor-pointer transition-[background-color,border-color,opacity] disabled:opacity-50 disabled:cursor-default ' +
    'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)] ' +
    'hover:brightness-[0.97] active:translate-y-px'
  );
}

export function buttonStyle(tone: ButtonTone = 'neutral') {
  if (tone === 'primary') {
    return {
      background: 'var(--color-accent)',
      color: 'var(--color-on-accent)',
      border: '1px solid var(--color-accent)',
    };
  }
  if (tone === 'danger') {
    return {
      background: 'var(--color-error)',
      color: 'var(--color-text-inverse)',
      border: '1px solid var(--color-error)',
    };
  }
  return {
    background: 'var(--color-bg-secondary)',
    color: 'var(--color-text)',
    border: '1px solid var(--color-border)',
  };
}
