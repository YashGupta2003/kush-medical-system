import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { VoiceCommandButton } from '../../src/components/VoiceCommandButton';
import { apiFetch } from '../../src/api/client';

vi.mock('../../src/api/client', () => ({
  apiFetch: vi.fn(),
  api: {}
}));

// Mock MediaDevices and MediaRecorder
const mockGetUserMedia = vi.fn();
const mockMediaRecorderStart = vi.fn();
const mockMediaRecorderStop = vi.fn();
const mockMediaRecorderInstances = [];

class MockMediaRecorder {
  constructor(stream, options) {
    this.stream = stream;
    this.options = options;
    this.state = 'inactive';
    mockMediaRecorderInstances.push(this);
  }
  start() {
    this.state = 'recording';
    mockMediaRecorderStart();
  }
  stop() {
    this.state = 'inactive';
    mockMediaRecorderStop();
    if (this.ondataavailable) {
      this.ondataavailable({ data: new Blob(['audio data']) });
    }
    if (this.onstop) {
      this.onstop();
    }
  }
}
MockMediaRecorder.isTypeSupported = vi.fn().mockReturnValue(true);

describe('VoiceCommandButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockMediaRecorderInstances.length = 0;
    
    Object.defineProperty(global.navigator, 'mediaDevices', {
      value: { getUserMedia: mockGetUserMedia },
      writable: true
    });
    
    global.MediaRecorder = MockMediaRecorder;
  });

  it('renders button and starts recording on click', async () => {
    mockGetUserMedia.mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] });
    
    render(<VoiceCommandButton onCommandParsed={vi.fn()} onError={vi.fn()} />);
    
    const btn = screen.getByRole('button');
    fireEvent.click(btn);
    
    await waitFor(() => {
      expect(mockGetUserMedia).toHaveBeenCalledWith({ audio: true });
      expect(mockMediaRecorderStart).toHaveBeenCalled();
    });
  });

  it('handles permission denied', async () => {
    mockGetUserMedia.mockRejectedValue(new Error("Denied"));
    const onError = vi.fn();
    
    render(<VoiceCommandButton onCommandParsed={vi.fn()} onError={onError} />);
    fireEvent.click(screen.getByRole('button'));
    
    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith("Microphone permission denied or unavailable.");
    });
  });

  it('stops recording and uploads audio', async () => {
    mockGetUserMedia.mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] });
    apiFetch.mockResolvedValue({ parsed: { intent: "sell" } });
    const onCommandParsed = vi.fn();
    
    render(<VoiceCommandButton onCommandParsed={onCommandParsed} onError={vi.fn()} />);
    const btn = screen.getByRole('button');
    
    // Start
    fireEvent.click(btn);
    await waitFor(() => expect(mockMediaRecorderStart).toHaveBeenCalled());
    
    // Stop
    fireEvent.click(btn);
    await waitFor(() => expect(mockMediaRecorderStop).toHaveBeenCalled());
    
    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith('/v1/voice/command', expect.objectContaining({
        method: 'POST',
      }));
      expect(onCommandParsed).toHaveBeenCalledWith({ parsed: { intent: "sell" } });
    });
  });
});
