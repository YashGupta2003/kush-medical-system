import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import UploadBill from "../../src/pages/UploadBill.jsx";
import ReviewBill from "../../src/pages/ReviewBill.jsx";
import { api } from "../../src/api/client.js";

vi.mock("../../src/api/client.js", () => ({
  api: {
    uploadBill: vi.fn(),
    uploadBillsBatch: vi.fn(),
    getBill: vi.fn(),
    getBillStatus: vi.fn(),
    processBillNow: vi.fn(),
    getBillImageUrl: vi.fn((id) => `/v1/bills/${id}/image`),
    getDistributorConfidence: vi.fn().mockResolvedValue(null),
    confirmBill: vi.fn(),
  },
}));

describe("UploadBill -> ReviewBill live redirect flow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects immediately to /review/:billId after single bill upload", async () => {
    api.uploadBill.mockResolvedValue({ bill_id: 42, task_id: "t-1", status: "queued", duplicate_warning: null });
    api.getBill.mockResolvedValue({
      id: 42,
      status: "queued",
      year: 2026,
      month: 11,
      uploaded_at: "2026-11-26T10:00:00Z",
      items: [],
    });
    api.getBillStatus.mockResolvedValue({ id: 42, status: "queued" });

    render(
      <MemoryRouter initialEntries={["/upload"]}>
        <Routes>
          <Route path="/upload" element={<UploadBill />} />
          <Route path="/review/:billId" element={<ReviewBill />} />
        </Routes>
      </MemoryRouter>
    );

    const fileInput = document.querySelector('input[type="file"]');
    const file = new File(["%PDF-1.4 demo"], "demo_bill.pdf", { type: "application/pdf" });
    fireEvent.change(fileInput, { target: { files: [file] } });
    fireEvent.submit(fileInput.closest("form"));

    await waitFor(() => {
      expect(screen.getByText(/Processing demo_bill\.pdf/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Live Extraction Pipeline/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Process OCR Immediately/i })).toBeInTheDocument();
  });

  it("allows instant Process OCR Immediately recovery on a queued bill and displays extracted items", async () => {
    api.getBill.mockResolvedValue({
      id: 25,
      status: "queued",
      year: 2026,
      month: 11,
      uploaded_at: "2026-11-26T10:00:00Z",
      items: [],
    });
    api.getBillStatus.mockResolvedValue({ id: 25, status: "queued" });
    api.processBillNow.mockResolvedValue({
      id: 25,
      status: "pending_review",
      distributor_id: 1,
      distributor_name: "Hari Krishna Distributor",
      invoice_no: "HK-101",
      year: 2026,
      month: 11,
      uploaded_at: "2026-11-26T10:00:00Z",
      items: [
        {
          id: 99,
          raw_name: "DOLO 650 TABLETS",
          medicine_id: 1,
          suggested_medicine_name: "DOLO 650 TABLETS",
          match_status: "auto",
          match_confidence: 100,
          qty: 20,
          free_qty: 2,
          rate: 26.8,
          mrp: 33.5,
          discount_pct: 0,
          special_discount_pct: 0,
          gst_pct: 5,
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/review/25"]}>
        <Routes>
          <Route path="/review/:billId" element={<ReviewBill />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Process OCR Immediately/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Process OCR Immediately/i }));

    await waitFor(() => {
      expect(screen.getByText(/Invoice Digitation Review/i)).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue("DOLO 650 TABLETS")).toBeInTheDocument();
  });
});
