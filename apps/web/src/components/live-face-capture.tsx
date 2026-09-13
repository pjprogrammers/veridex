"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Camera,
  RefreshCw,
  SwitchCamera,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Simulated live-face capture.
 *
 * The prototype's real face pipeline is not reliable yet, so this presents a
 * camera-like UI over a fixed reference image (the synthetic Piyush Aadhaar
 * portrait). Pressing the shutter "captures" that image and hands it to the
 * caller as the live face, which the demo verification then reports as a match.
 *
 * No `getUserMedia` / real camera device is ever accessed.
 */
const DEFAULT_FEED = "/demo/piyush.jpeg";
const STARTUP_MS = 900;

interface LiveFaceCaptureProps {
  open: boolean;
  onClose: () => void;
  onCapture: (file: File) => void | Promise<void>;
  /** Simulated camera feed image. Defaults to the Piyush demo portrait. */
  feedSrc?: string;
  /** Filename handed to the backend for the captured frame. */
  fileName?: string;
  subject?: string;
}

export function LiveFaceCapture({
  open,
  onClose,
  onCapture,
  feedSrc = DEFAULT_FEED,
  fileName,
  subject,
}: LiveFaceCaptureProps) {
  const [booting, setBooting] = useState(true);
  const [flash, setFlash] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [clock, setClock] = useState(() => new Date());
  const capturedRef = useRef(false);

  useEffect(() => {
    if (!open) return;
    setBooting(true);
    setCapturing(false);
    capturedRef.current = false;
    const t = setTimeout(() => setBooting(false), STARTUP_MS);
    return () => clearTimeout(t);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const id = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(id);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const capture = useCallback(async () => {
    if (capturing || booting || capturedRef.current) return;
    capturedRef.current = true;
    setCapturing(true);
    setFlash(true);
    await new Promise((r) => setTimeout(r, 180));
    setFlash(false);
    try {
      const resp = await fetch(feedSrc);
      if (!resp.ok) throw new Error("capture feed unavailable");
      const blob = await resp.blob();
      const type = blob.type || (feedSrc.endsWith(".jpg") || feedSrc.endsWith(".jpeg") ? "image/jpeg" : "image/png");
      const name =
        fileName ??
        `live_capture_${new Date().toISOString().replace(/[:.]/g, "-")}.${
          type === "image/png" ? "png" : "jpg"
        }`;
      await onCapture(new File([blob], name, { type }));
    } finally {
      setCapturing(false);
      onClose();
    }
  }, [booting, capturing, feedSrc, fileName, onCapture, onClose]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Live face capture (simulated)"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm"
    >
      <div className="w-full max-w-md overflow-hidden rounded-2xl border border-white/10 bg-neutral-950 shadow-2xl">
        {/* Top status bar */}
        <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-2.5 text-[11px] font-medium tracking-wide text-white/80">
          <span className="inline-flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-500/70" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-red-500" />
            </span>
            SIMULATED CAMERA
          </span>
          <span className="font-mono text-white/50">
            {clock.toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })}
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close camera"
            className="rounded-md p-1 text-white/70 transition-colors hover:bg-white/10 hover:text-white"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        {/* Viewfinder */}
        <div className="relative aspect-[4/3] w-full overflow-hidden bg-black">
          {booting ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-white/70">
              <RefreshCw className="h-6 w-6 animate-spin" aria-hidden />
              <span className="text-xs tracking-wide">
                Initializing front camera…
              </span>
            </div>
          ) : (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={feedSrc}
                alt={subject ? `Simulated live face — ${subject}` : "Simulated live face"}
                className="h-full w-full scale-105 object-cover"
              />
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_35%,rgba(0,0,0,0.55)_100%)]" />
            </>
          )}

          {/* Face guide overlay */}
          {!booting ? (
            <div className="pointer-events-none absolute inset-0">
              <div className="absolute left-1/2 top-1/2 h-[62%] w-[46%] -translate-x-1/2 -translate-y-1/2 rounded-[50%] border-2 border-dashed border-white/45" />
              <Corner className="left-4 top-4 border-l-2 border-t-2" />
              <Corner className="right-4 top-4 border-r-2 border-t-2" />
              <Corner className="bottom-4 left-4 border-b-2 border-l-2" />
              <Corner className="bottom-4 right-4 border-b-2 border-r-2" />
              <div className="absolute inset-x-0 bottom-3 text-center text-[10px] font-medium tracking-wide text-white/70">
                Align face within the oval
              </div>
            </div>
          ) : null}

          {/* Shutter flash */}
          <div
            className={cn(
              "pointer-events-none absolute inset-0 bg-white transition-opacity duration-150",
              flash ? "opacity-90" : "opacity-0",
            )}
          />

          {/* Recording badge */}
          {!booting ? (
            <div className="absolute left-4 top-4 flex items-center gap-1.5 rounded-full bg-black/50 px-2 py-1 text-[10px] font-semibold tracking-wide text-white/90">
              <Camera className="h-3 w-3" aria-hidden />
              FRONT
            </div>
          ) : null}
        </div>

        {/* Controls */}
        <div className="flex items-center justify-between gap-4 px-6 py-5">
          <span className="w-10" aria-hidden />
          <button
            type="button"
            onClick={capture}
            disabled={booting || capturing}
            aria-label="Capture face"
            className={cn(
              "relative flex h-16 w-16 items-center justify-center rounded-full border-4 border-white/80 transition-transform active:scale-95",
              booting || capturing
                ? "cursor-not-allowed opacity-50"
                : "hover:scale-105",
            )}
          >
            <span
              className={cn(
                "h-12 w-12 rounded-full bg-white transition-colors",
                capturing && "bg-red-500",
              )}
            />
          </button>
          <span
            className="flex w-10 items-center justify-center text-white/35"
            aria-hidden
          >
            <SwitchCamera className="h-5 w-5" />
          </span>
        </div>

        <div className="border-t border-white/10 px-4 py-2.5 text-center text-[10px] leading-relaxed text-white/45">
          SYNTHETIC DEMO — no physical camera is accessed. Capturing reuses the
          reference portrait for the face-similarity comparison.
        </div>
      </div>
    </div>
  );
}

function Corner({ className }: { className: string }) {
  return (
    <span
      className={cn("absolute h-6 w-6 border-white/60", className)}
      aria-hidden
    />
  );
}
