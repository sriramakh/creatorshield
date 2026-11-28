export const THEME_KEY = "cs-theme";
export const SIDEBAR_KEY = "cs-sidebar";

/**
 * Inline script for <head>: applies the saved theme (or the OS preference) and the saved
 * sidebar width before the first paint, so neither flashes on load.
 */
export const THEME_SCRIPT = `(function(){var d=document.documentElement;try{var v=localStorage.getItem("${THEME_KEY}");var k=v==="dark"||(v!=="light"&&window.matchMedia("(prefers-color-scheme: dark)").matches);d.dataset.theme=k?"dark":"light";d.dataset.sidebar=localStorage.getItem("${SIDEBAR_KEY}")==="collapsed"?"collapsed":"expanded";}catch(e){d.dataset.theme="light";d.dataset.sidebar="expanded";}})();`;
