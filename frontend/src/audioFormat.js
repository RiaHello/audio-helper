const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm"];

export const MIN_DURATION_MS = 1000;
export const MAX_DURATION_MS = 60_000;
export const MAX_FILE_BYTES = 5 * 1024 * 1024;

export function pickSupportedMimeType() {
  if (typeof MediaRecorder === "undefined") {
    return null;
  }

  return MIME_CANDIDATES.find((type) => MediaRecorder.isTypeSupported(type)) ?? null;
}

export function formatDuration(ms) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

export function formatFileSize(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function buildRecordingFilename(mimeType, recordedAt = new Date()) {
  const stamp = [
    recordedAt.getFullYear(),
    String(recordedAt.getMonth() + 1).padStart(2, "0"),
    String(recordedAt.getDate()).padStart(2, "0"),
    "-",
    String(recordedAt.getHours()).padStart(2, "0"),
    String(recordedAt.getMinutes()).padStart(2, "0"),
    String(recordedAt.getSeconds()).padStart(2, "0"),
  ].join("");
  const extension = mimeType?.includes("webm") ? "webm" : "webm";
  return `meetup-recording-${stamp}.${extension}`;
}

export function describeMediaError(error) {
  const name = error?.name;
  if (name === "NotAllowedError" || name === "PermissionDeniedError") {
    return "麦克风权限被拒绝，请在浏览器中允许使用麦克风后重试。";
  }
  if (name === "NotFoundError" || name === "DevicesNotFoundError") {
    return "未检测到麦克风，请连接设备后重试。";
  }
  if (name === "NotReadableError" || name === "TrackStartError") {
    return "麦克风被占用或无法读取，请关闭其他应用后重试。";
  }
  return "无法开始录音，请检查麦克风后重试。";
}
