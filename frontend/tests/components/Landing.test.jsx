import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Landing from "../../src/pages/Landing";

describe("Landing page interactive workbench and dual theme", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("renders hero, CTAs, and switches interactive module tabs and scenarios cleanly", async () => {
    render(
      <MemoryRouter>
        <Landing />
      </MemoryRouter>
    );

    expect(screen.getByText(/The Intelligent OS for/i)).toBeInTheDocument();
    expect(screen.getByText(/Duplicate Active Ingredient Guardrail Triggered/i)).toBeInTheDocument();

    // Switch live POS scenario pill
    fireEvent.click(screen.getByRole("button", { name: /PAN-D \+ Shelcal 500/i }));
    await waitFor(() => {
      expect(screen.getByText(/No Clinical Conflicts Found/i)).toBeInTheDocument();
    });

    // Switch workbench tabs
    fireEvent.click(screen.getByRole("tab", { name: /Bill OCR Engine/i }));
    await waitFor(() => {
      expect(screen.getByText(/Hari Krishna Distributor — Invoice #HK-8842/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("tab", { name: /PharmaCopilot AI/i }));
    await waitFor(() => {
      expect(screen.getByText(/GROQ ALLOWLIST TOOL TRACE/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("tab", { name: /TrustChain Ledger/i }));
    await waitFor(() => {
      expect(screen.getByText(/TrustChain Immutable Audit Ledger/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Session-Level Tenant Isolation/i)).toBeInTheDocument();
    expect(screen.getByText(/K-Anonymity Pulse/i)).toBeInTheDocument();
  });

  it("toggles cleanly between light and dark theme", async () => {
    const { container } = render(
      <MemoryRouter>
        <Landing />
      </MemoryRouter>
    );

    const root = container.querySelector(".landing-root");
    expect(root.getAttribute("data-landing-theme")).toBe("light");

    fireEvent.click(screen.getByRole("button", { name: /Switch to dark mode/i }));
    await waitFor(() => {
      expect(root.getAttribute("data-landing-theme")).toBe("dark");
      expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    });

    fireEvent.click(screen.getByRole("button", { name: /Switch to light mode/i }));
    await waitFor(() => {
      expect(root.getAttribute("data-landing-theme")).toBe("light");
      expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    });
  });
});
