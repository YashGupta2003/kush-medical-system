import { useEffect, useState } from "react";

export const THEME_STORAGE_KEY = "pharmos_theme";

export function resolveInitialTheme() {
  if (typeof window === "undefined") return "light";
  try {
    const saved = window.localStorage?.getItem(THEME_STORAGE_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // ignore storage errors
  }
  const attr = document.documentElement.getAttribute("data-theme");
  if (attr === "light" || attr === "dark") return attr;
  return "light";
}

/** Shared Light/Dark theme state synced with documentElement[data-theme] and localStorage. */
export function useTheme() {
  const [theme, setTheme] = useState(resolveInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      window.localStorage?.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // ignore storage errors
    }
  }, [theme]);

  const toggleTheme = (e) => {
    const next = theme === "dark" ? "light" : "dark";
    try {
      window.localStorage?.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // ignore storage errors
    }
    if (!document.startViewTransition) {
      document.documentElement.setAttribute("data-theme", next);
      setTheme(next);
      return;
    }
    const x = e?.clientX || window.innerWidth / 2;
    const y = e?.clientY || 0;
    const endRadius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
    const transition = document.startViewTransition(() => {
      document.documentElement.setAttribute("data-theme", next);
      setTheme(next);
    });
    transition.ready
      .then(() => {
        const clipPath = [`circle(0px at ${x}px ${y}px)`, `circle(${endRadius}px at ${x}px ${y}px)`];
        document.documentElement.animate(
          { clipPath: next === "dark" ? clipPath : [...clipPath].reverse() },
          {
            duration: 450,
            easing: "ease-in-out",
            pseudoElement: next === "dark" ? "::view-transition-new(root)" : "::view-transition-old(root)",
          }
        );
      })
      .catch(() => {});
  };

  return { theme, toggleTheme };
}

export const useLandingTheme = useTheme;
