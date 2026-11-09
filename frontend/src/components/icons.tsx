import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;
const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  viewBox: "0 0 24 24",
};

export const ShieldIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M12 3l7 3v6c0 4.2-2.9 7.9-7 9-4.1-1.1-7-4.8-7-9V6l7-3z" />
    <path d="M9 12l2 2 4-4" />
  </svg>
);
export const UploadIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M12 16V4m0 0l-4 4m4-4l4 4" />
    <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
  </svg>
);
export const ClockIcon = (p: P) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);
export const ExternalIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M14 4h6v6M20 4l-9 9" />
    <path d="M18 14v4a2 2 0 01-2 2H6a2 2 0 01-2-2V8a2 2 0 012-2h4" />
  </svg>
);
export const DownloadIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M12 4v12m0 0l-4-4m4 4l4-4" />
    <path d="M4 18v1a1 1 0 001 1h14a1 1 0 001-1v-1" />
  </svg>
);
export const AlertIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M12 9v4m0 4h.01" />
    <path d="M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z" />
  </svg>
);
export const CheckIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M5 12l5 5L20 7" />
  </svg>
);
export const UserCheckIcon = (p: P) => (
  <svg {...base} {...p}>
    <circle cx="9" cy="8" r="4" />
    <path d="M2 21a7 7 0 0114 0M16 11l2 2 4-4" />
  </svg>
);
export const TrashIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />
  </svg>
);
export const PlayIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M7 5v14l11-7z" />
  </svg>
);
export const DocIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5z" />
    <path d="M14 3v5h5M9 13h6M9 17h6" />
  </svg>
);
export const MusicIcon = (p: P) => (
  <svg {...base} {...p}>
    <path d="M9 18V5l11-2v13" />
    <circle cx="6" cy="18" r="3" />
    <circle cx="17" cy="16" r="3" />
  </svg>
);
export const GlobeIcon = (p: P) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z" />
  </svg>
);
export const SearchIcon = (p: P) => (
  <svg {...base} {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="M20 20l-4-4" />
  </svg>
);
