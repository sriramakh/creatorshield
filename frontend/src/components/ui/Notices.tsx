"use client";

import { RefreshCw } from "lucide-react";
import { Button } from "./Button";
import { Callout } from "./Callout";

/** A failure with optional Retry and Dismiss actions (announced as an alert). */
export function ErrorNotice({
  title,
  message,
  onRetry,
  onDismiss,
  note,
  className,
}: {
  title: string;
  message: string;
  onRetry?: () => void;
  onDismiss?: () => void;
  note?: string;
  className?: string;
}) {
  return (
    <Callout
      tone="danger"
      title={title}
      className={className}
      action={
        onRetry || onDismiss ? (
          <>
            {onRetry && (
              <Button size="sm" variant="secondary" leadingIcon={<RefreshCw />} onClick={onRetry}>
                Retry
              </Button>
            )}
            {onDismiss && (
              <Button size="sm" variant="ghost" onClick={onDismiss}>
                Dismiss
              </Button>
            )}
          </>
        ) : undefined
      }
    >
      <p>{message}</p>
      {note && <p className="mt-0.5 text-[13px] text-ink-3">{note}</p>}
    </Callout>
  );
}

/** Shown when the API rejected the stored login (HTTP 401). Reloading lets the browser ask again. */
export function SignInRequired() {
  return (
    <Callout
      tone="danger"
      title="Sign-in needed"
      action={
        <Button size="sm" variant="secondary" onClick={() => window.location.reload()}>
          Reload and sign in
        </Button>
      }
    >
      Your login was not accepted. It may have been changed or expired. Reload the page to sign in again.
    </Callout>
  );
}
