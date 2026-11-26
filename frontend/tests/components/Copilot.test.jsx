import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Copilot from "../../src/pages/Copilot.jsx";
import { api } from "../../src/api/client.js";

vi.mock("../../src/api/client.js", () => ({
  api: {
    sendCopilotMessage: vi.fn(),
  },
}));

describe("PharmaCopilot redesigned studio", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it("renders playbooks, tool telemetry rail, and prompt cards in empty state", () => {
    render(
      <MemoryRouter>
        <Copilot />
      </MemoryRouter>
    );

    expect(screen.getByText("PharmaCopilot")).toBeInTheDocument();
    expect(screen.getByText(/Ask anything about your pharmacy/i)).toBeInTheDocument();
    expect(screen.getByText(/19 Live Tools Wired/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Which medicines expire in the next 30 days\?/i).length).toBeGreaterThanOrEqual(1);
  });

  it("sends query, displays markdown reply with tool badges, and clears chat cleanly", async () => {
    api.sendCopilotMessage.mockResolvedValue({
      reply: "**2 batches expiring soon**\n\n| Medicine | Days |\n|---|---|\n| PACIMOL 650 | 2 |",
      tool_calls: [{ tool: "get_expiring_medicines", input: { days: 30 } }],
      history: [{ role: "user", content: "Which medicines expire in the next 30 days?" }],
    });

    render(
      <MemoryRouter>
        <Copilot />
      </MemoryRouter>
    );

    const textarea = screen.getByPlaceholderText(/Ask about expiring batches/i);
    fireEvent.change(textarea, { target: { value: "Expiring batches?" } });
    fireEvent.click(screen.getByRole("button", { name: /Send/i }));

    await waitFor(() => {
      expect(screen.getByText(/PACIMOL 650/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/Checked expiring medicines/i)).toBeInTheDocument();
    expect(api.sendCopilotMessage).toHaveBeenCalledWith("Expiring batches?", []);

    const resetBtn = screen.getByRole("button", { name: /New Chat/i });
    fireEvent.click(resetBtn);
    expect(screen.getByText(/Ask anything about your pharmacy/i)).toBeInTheDocument();
  });
});
