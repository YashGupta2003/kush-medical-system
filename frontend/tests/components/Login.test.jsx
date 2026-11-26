import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Login from "../../src/pages/Login";

vi.mock("../../src/auth/AuthContext.jsx", () => ({
  useAuth: () => ({ login: vi.fn() }),
}));

describe("Login page", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("renders split auth layout, password toggle, theme toggle, and registration link", () => {
    const { container } = render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { level: 1, name: /Welcome back to PharmOS Command/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: /PharmOS/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sign in to Workspace/i })).toBeInTheDocument();

    const regLink = screen.getByRole("link", { name: /Create a shop account/i });
    expect(regLink).toHaveAttribute("href", "/register");

    const pwInput = screen.getByLabelText("Password");
    expect(pwInput).toHaveAttribute("type", "password");
    fireEvent.click(screen.getByRole("button", { name: /Show password/i }));
    expect(pwInput).toHaveAttribute("type", "text");

    const root = container.querySelector(".landing-root");
    expect(root.getAttribute("data-landing-theme")).toBe("light");
    fireEvent.click(screen.getByRole("button", { name: /Switch to dark mode/i }));
    expect(root.getAttribute("data-landing-theme")).toBe("dark");
  });
});
