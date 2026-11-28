"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Tooltip } from "./Tooltip";

/** Icon-only button: always labelled, always with a tooltip. */
export function IconButton({
  label,
  icon,
  size = "md",
  variant = "ghost",
  tooltip = true,
  className,
  type = "button",
  ...rest
}: {
  label: string;
  icon: ReactNode;
  size?: "sm" | "md";
  variant?: "ghost" | "secondary";
  tooltip?: boolean;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children" | "aria-label">) {
  const button = (
    <button
      type={type}
      aria-label={label}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-[6px] text-ink-2 transition-colors duration-[120ms]",
        "hover:bg-surface-3 hover:text-ink disabled:cursor-not-allowed disabled:opacity-50 [&_svg]:size-4",
        size === "sm" ? "size-7" : "size-9",
        variant === "secondary" && "border border-line-strong bg-surface",
        className,
      )}
      {...rest}
    >
      {icon}
    </button>
  );
  return tooltip ? <Tooltip content={label}>{button}</Tooltip> : button;
}
