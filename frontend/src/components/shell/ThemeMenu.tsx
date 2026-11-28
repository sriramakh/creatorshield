"use client";

import { Check, Monitor, Moon, Sun } from "lucide-react";
import { setTheme, useResolvedTheme, useThemeChoice, type ThemeChoice } from "@/lib/theme";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger, Tooltip } from "../ui";

const OPTIONS: { value: ThemeChoice; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "Match system", icon: Monitor },
];

export function ThemeMenu({ side = "top" }: { side?: "top" | "bottom" }) {
  const choice = useThemeChoice();
  const resolved = useResolvedTheme();
  const Icon = resolved === "dark" ? Moon : Sun;
  return (
    <DropdownMenu>
      <Tooltip content="Theme">
        <DropdownMenuTrigger
          aria-label="Theme"
          className="inline-flex size-8 shrink-0 items-center justify-center rounded-[6px] text-ink-2 hover:bg-surface-3 hover:text-ink"
        >
          <Icon className="size-4" aria-hidden />
        </DropdownMenuTrigger>
      </Tooltip>
      <DropdownMenuContent side={side} align="start" className="min-w-44">
        <DropdownMenuLabel>Theme</DropdownMenuLabel>
        {OPTIONS.map((o) => (
          <DropdownMenuItem key={o.value} icon={<o.icon />} onSelect={() => setTheme(o.value)}>
            <span className="flex-1">{o.label}</span>
            {choice === o.value && <Check className="!text-accent" aria-label="selected" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
