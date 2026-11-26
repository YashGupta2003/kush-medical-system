import { useEffect, useState } from "react";

export function resolveInitialTheme() {
  if (typeof window === "undefined") return "light";
  const attr = document.documentElement.getAttribute("data-theme");
  if (attr === "light" || attr === "dark") return attr;
  const saved = window.localStorage?.getItem("pharmos_theme");
  if (saved === "light" || saved === "dark") return saved;
  if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

/** Shared Light/Dark theme state synced with documentElement[data-theme] and localStorage. */
export function useLandingTheme() {
  const [theme, setTheme] = useState(resolveInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      window.localStorage?.setItem("pharmos_theme", theme);
    } catch {
      // ignore storage errors
    }
  }, [theme]);

  const toggleTheme = (e) => {
    const next = theme === "dark" ? "light" : "dark";
    if (!document.startViewTransition) {
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
