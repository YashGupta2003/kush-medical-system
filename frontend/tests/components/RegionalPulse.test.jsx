import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import RegionalPulse from "../../src/pages/RegionalPulse";
import { api } from "../../src/api/client";

vi.mock("../../src/api/client", () => ({
  api: {
    getRegionalHeatmap: vi.fn(),
    getRegionHeatmap: vi.fn(),
    refreshRegionalHeatmap: vi.fn(),
  },
}));

vi.mock("../../src/auth/AuthContext", () => ({
  useAuth: () => ({ isOwner: false }),
}));

const heatmap = (overrides = {}) => ({
  as_of: "2026-11-18T21:15:00Z",
  window_start: "2026-11-12",
  window_end: "2026-11-18",
  window_days: 7,
  privacy: {
    min_contributors: 3,
    aggregation: "region_condition_7d",
    individual_data_included: false,
  },
  suppressed_cells: 2,
  cells: [
    {
      region_code: "MH-PUNE",
      condition_name: "Fever",
      signal_level: "elevated",
      trend: "up",
      trend_labels: ["stable", "stable", "watch", "watch", "elevated", "elevated", "elevated"],
      contributor_count: 5,
      public_volume_band: "high",
      confidence: "medium",
      privacy_safe: true,
    },
  ],
  notice: "Public-health signal for awareness only; not a medical diagnosis.",
  ...overrides,
});

describe("RegionalPulse privacy UI", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getRegionHeatmap.mockResolvedValue({ cells: [] });
    api.getRegionalHeatmap.mockResolvedValue(heatmap());
  });

  it("always shows the privacy badge and the 3-pharmacy rule", async () => {
    render(<RegionalPulse />);
    await waitFor(() => expect(api.getRegionalHeatmap).toHaveBeenCalled());

    expect(screen.getByText("Privacy protected")).toBeInTheDocument();
    expect(screen.getByText("At least 3 pharmacies required")).toBeInTheDocument();
  });

  it("shows signal level as text and shape, never color alone", async () => {
    render(<RegionalPulse />);
    await waitFor(() => expect(api.getRegionalHeatmap).toHaveBeenCalled());

    const cell = await screen.findByRole("button", { name: /Fever in Pune: elevated/i });
    expect(cell).toHaveTextContent("▲ elevated");
    expect(cell).toHaveTextContent("5 pharmacies");
  });

  it("tooltip shows contributor count but no shop identity or raw units", async () => {
    render(<RegionalPulse />);
    await waitFor(() => expect(api.getRegionalHeatmap).toHaveBeenCalled());

    await screen.findByRole("button", { name: /Fever in Pune: elevated/i });
    const tooltip = document.querySelector('[role="tooltip"]');
    expect(tooltip).not.toBeNull();
    expect(tooltip).toHaveTextContent("5 contributing pharmacies");
    expect(tooltip).toHaveTextContent("No shop, customer, or medicine identity is shown.");
    expect(tooltip).not.toHaveTextContent("Fever Shop");
    expect(tooltip).not.toHaveTextContent("otc_units");
    expect(tooltip).not.toHaveTextContent("total_units");
  });

  it("suppressed cells are non-interactive and explained", async () => {
    render(<RegionalPulse />);
    await waitFor(() => expect(api.getRegionalHeatmap).toHaveBeenCalled());

    expect(screen.getByText(/Hidden to protect privacy/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Hidden to protect privacy/i })).not.toBeInTheDocument();
  });

  it("empty state explains the privacy rule", async () => {
    api.getRegionalHeatmap.mockResolvedValueOnce(heatmap({
      cells: [],
      suppressed_cells: 4,
    }));

    render(<RegionalPulse />);
    await waitFor(() => expect(api.getRegionalHeatmap).toHaveBeenCalled());

    expect(await screen.findByText("Not enough contributions yet")).toBeInTheDocument();
    expect(screen.getByText(/hidden to protect privacy until 3 pharmacies contribute/i)).toBeInTheDocument();
  });
});
