import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { VoiceConfirmationCard } from '../../src/components/VoiceConfirmationCard';
import { apiFetch } from '../../src/api/client';

vi.mock('../../src/api/client', () => ({
  apiFetch: vi.fn(),
  api: {}
}));

describe('VoiceConfirmationCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders parsed info and confirms', async () => {
    apiFetch.mockResolvedValue({ status: "success" });
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    
    const parsedResult = {
      parsed: {
        intent: "sell",
        quantity: 2,
        unit: "strip",
        confidence: 0.95,
        raw_transcript: "sell 2 strips of crocin"
      },
      resolved_medicine: {
        id: 1,
        name: "CROCIN 500",
      },
      requires_confirmation: true
    };

    render(
      <VoiceConfirmationCard 
        parsedResult={parsedResult} 
        onConfirm={onConfirm} 
        onCancel={onCancel} 
      />
    );

    expect(screen.getByText(/Samjha:/)).toBeInTheDocument();
    expect(screen.getByText(/CROCIN 500/)).toBeInTheDocument();
    expect(screen.getByText(/sell 2 strips of crocin/)).toBeInTheDocument();

    const confirmBtn = screen.getByRole('button', { name: "Confirm" });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith('/v1/voice/confirm', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ intent: "sell", medicine_id: 1, quantity: 2 })
      }));
      expect(onConfirm).toHaveBeenCalled();
    });
  });

  it('renders edit form when unclear and allows edit', async () => {
    apiFetch.mockResolvedValue({ status: "success" });
    const onConfirm = vi.fn();
    
    const parsedResult = {
      parsed: {
        intent: "unclear",
        quantity: 1,
        unit: "strip",
        confidence: 0.1,
        raw_transcript: "mumble mumble"
      },
      resolved_medicine: {
        id: 1,
        name: "CROCIN 500"
      },
      requires_confirmation: true,
      message: "Command was unclear"
    };

    render(
      <VoiceConfirmationCard 
        parsedResult={parsedResult} 
        onConfirm={onConfirm} 
        onCancel={vi.fn()} 
      />
    );

    expect(screen.getByText(/Command was unclear/)).toBeInTheDocument();
    
    const qtyInput = screen.getByRole('spinbutton');
    fireEvent.change(qtyInput, { target: { value: '5' } });

    const confirmBtn = screen.getByRole('button', { name: "Confirm" });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith('/v1/voice/confirm', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ intent: "sell", medicine_id: 1, quantity: 5 }) // default intent when unclear is 'sell'
      }));
    });
  });

  it('handles cancel', () => {
    const onCancel = vi.fn();
    const parsedResult = {
      parsed: { intent: "sell", quantity: 1, unit: "strip", confidence: 0.9, raw_transcript: "" },
      resolved_medicine: { id: 1, name: "TEST" }
    };

    render(<VoiceConfirmationCard parsedResult={parsedResult} onConfirm={vi.fn()} onCancel={onCancel} />);
    
    fireEvent.click(screen.getByRole('button', { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalled();
  });
});
