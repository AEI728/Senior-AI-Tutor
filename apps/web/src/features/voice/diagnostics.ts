import type { AudioOwner } from "./media";

export type AudioReport = {
  owner: AudioOwner;
  phase: string;
  updatedAt: string;
  samples?: number;
  peak?: number;
  engine?: string;
  characters?: number;
  code?: string;
  device?: string;
  channels?: number;
  inputMode?: string;
  trackMuted?: boolean;
  avoidedDevice?: string;
};
export function readAudioReport(owner: AudioOwner): AudioReport | null {
  try { return JSON.parse(sessionStorage.getItem("xiaoban-audio-report-" + owner) || "null"); }
  catch { return null; }
}
// Local aggregate diagnostics only: no recording, transcript, reply, token or device ID.
export function audioReport(owner: AudioOwner, changes: Partial<AudioReport>) {
  const value = { ...readAudioReport(owner), owner, ...changes, updatedAt: new Date().toISOString() };
  try { sessionStorage.setItem("xiaoban-audio-report-" + owner, JSON.stringify(value)); }
  catch { /* A disabled browser store must not prevent capture. */ }
  window.dispatchEvent(new CustomEvent("xiaoban-audio-report", { detail: value }));
}
