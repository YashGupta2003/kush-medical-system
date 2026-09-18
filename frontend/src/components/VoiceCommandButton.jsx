import { useState, useRef, useEffect } from "react";
import { apiFetch } from "../api/client";

export function VoiceCommandButton({ onCommandParsed, onError }) {
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  // max_voice_clip_seconds is 12s on backend
  const MAX_RECORDING_MS = 12000;

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      let mimeType = "audio/webm";
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        if (MediaRecorder.isTypeSupported("audio/mp4")) mimeType = "audio/mp4";
        else if (MediaRecorder.isTypeSupported("audio/ogg")) mimeType = "audio/ogg";
        else mimeType = ""; // fallback to default
      }

      const options = mimeType ? { mimeType } : undefined;
      const mediaRecorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        setRecording(false);
        setProcessing(true);

        const audioBlob = new Blob(audioChunksRef.current, {
          type: mediaRecorder.mimeType || "audio/webm",
        });

        try {
          const formData = new FormData();
          formData.append("audio_file", audioBlob, "voice_command.webm");

          const result = await apiFetch("/v1/voice/command", {
            method: "POST",
            body: formData,
            // don't set Content-Type header; fetch sets it automatically with boundary for FormData
          });
          onCommandParsed(result);
        } catch (err) {
          onError(err.message || "Failed to process voice command.");
        } finally {
          setProcessing(false);
        }
      };

      mediaRecorder.start();
      setRecording(true);

      // Auto stop after MAX_RECORDING_MS
      setTimeout(() => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
          mediaRecorderRef.current.stop();
        }
      }, MAX_RECORDING_MS);
    } catch (err) {
      onError("Microphone permission denied or unavailable.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  };

  return (
    <div className="voice-btn-container">
      <button
        type="button"
        className={`voice-btn ${recording ? "recording" : ""} ${processing ? "processing" : ""}`}
        onClick={recording ? stopRecording : startRecording}
        disabled={processing}
        title={recording ? "Tap to stop" : "Tap to speak command"}
      >
        {processing ? (
          <span className="spinner"></span>
        ) : recording ? (
          <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="6" y="6" width="12" height="12" rx="2" ry="2"></rect>
          </svg>
        ) : (
          <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
            <line x1="12" y1="19" x2="12" y2="23"></line>
            <line x1="8" y1="23" x2="16" y2="23"></line>
          </svg>
        )}
      </button>

      <style>{`
        .voice-btn-container {
          display: inline-flex;
          align-items: center;
          margin-left: 8px;
        }
        .voice-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 44px;
          height: 44px;
          border-radius: 50%;
          border: 1px solid var(--border);
          background: var(--bg-surface);
          color: var(--text-main);
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .voice-btn:hover:not(:disabled) {
          border-color: var(--primary-500);
          color: var(--primary-500);
        }
        .voice-btn.recording {
          background: rgba(239, 68, 68, 0.1);
          border-color: var(--danger);
          color: var(--danger);
          animation: pulse 1.5s infinite;
        }
        .voice-btn.processing {
          opacity: 0.7;
          cursor: not-allowed;
        }
        .spinner {
          width: 20px;
          height: 20px;
          border: 2px solid var(--border);
          border-top-color: var(--primary-500);
          border-radius: 50%;
          animation: spin 0.7s linear infinite;
        }
        @keyframes pulse {
          0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
          70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
          100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
