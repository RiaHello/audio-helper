import { formatDuration } from "../audioFormat.js";

export default function RecordButton({
  supported,
  status,
  elapsedMs,
  onHoldStart,
}) {
  const recording = status === "recording" || status === "requesting";
  const label = status === "recording" ? "松开结束" : "按住说话";

  function handlePointerDown(event) {
    if (!supported || recording) {
      return;
    }
    if (event.pointerType === "mouse" && event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    onHoldStart();
  }

  function handleContextMenu(event) {
    event.preventDefault();
  }

  return (
    <div className="record-wrap">
      <button
        type="button"
        className={recording ? "record-button is-recording" : "record-button"}
        disabled={!supported}
        aria-pressed={recording}
        onPointerDown={handlePointerDown}
        onContextMenu={handleContextMenu}
      >
        <span className="record-dot" />
        {label}
      </button>
      <p className="record-time" aria-live="polite">
        {status === "recording"
          ? `${formatDuration(elapsedMs)} / 01:00`
          : "1 到 60 秒，松开或满 60 秒结束"}
      </p>
    </div>
  );
}
