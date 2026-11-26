import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import ThemeToggle from "../../src/components/ThemeToggle.jsx";
import { resolveInitialTheme, THEME_STORAGE_KEY } from "../../src/utils/theme.js";

describe("ThemeToggle & persistence", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("defaults to light mode even if OS prefers dark, and persists user toggle across reloads", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation(() => ({
        matches: true,
        media: "(prefers-color-scheme: dark)",
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }))
    );

    expect(resolveInitialTheme()).toBe("light");

    const { unmount } = render(<ThemeToggle />);
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");

    fireEvent.click(screen.getByRole("button", { name: /Switch to dark mode/i }));
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");

    // Simulate reload: clear attribute and remount
    unmount();
    document.documentElement.removeAttribute("data-theme");
    render(<ThemeToggle />);
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");

    // Switch back to light and verify persistence on another simulated reload
    fireEvent.click(screen.getByRole("button", { name: /Switch to light mode/i }));
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");

    vi.unstubAllGlobals();
  });
});
