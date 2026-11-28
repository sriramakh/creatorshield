"use client";

import { useSyncExternalStore } from "react";
import { isAuthRequired, subscribeAuthRequired } from "@/lib/api";
import { SignInRequired } from "./ui";

/** One app-wide notice once any API call has answered 401. */
export function AuthNotice() {
  const required = useSyncExternalStore(subscribeAuthRequired, isAuthRequired, () => false);
  if (!required) return null;
  return (
    <div className="mb-6">
      <SignInRequired />
    </div>
  );
}
