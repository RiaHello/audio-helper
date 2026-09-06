import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  MAX_DURATION_MS,
  MAX_FILE_BYTES,
  MIN_DURATION_MS,
  buildRecordingFilename,
  describeMediaError,
  pickSupportedMimeType,
} from "./audioFormat.js";

function stopTracks(stream) {
  if (!stream) {
    return;
  }
  for (const track of stream.getTracks()) {
    track.stop();
  }
}

export function useRecorder() {
  const mimeType = useMemo(() => pickSupportedMimeType(), []);
  const supported = mimeType !== null;
  const sessionRef = useRef(null);
  const clipUrlRef = useRef(null);

  const [status, setStatus] = useState("idle");
  const [message, setMessage] = useState(
    supported ? null : "当前浏览器不支持 WebM/Opus 录音，请更换 Chrome、Edge 或 Firefox。",
  );
  const [elapsedMs, setElapsedMs] = useState(0);
  const [clip, setClip] = useState(null);

  const clearSessionTimers = useCallback((session) => {
    if (!session) {
      return;
    }
    window.clearTimeout(session.maxTimer);
    window.clearInterval(session.tick);
  }, []);

  const replaceClip = useCallback((nextClip) => {
    if (clipUrlRef.current) {
      URL.revokeObjectURL(clipUrlRef.current);
      clipUrlRef.current = null;
    }
    if (nextClip?.url) {
      clipUrlRef.current = nextClip.url;
    }
    setClip(nextClip);
  }, []);

  const finalizeSession = useCallback(
    (session) => {
      clearSessionTimers(session);
      stopTracks(session.stream);
      if (sessionRef.current === session) {
        sessionRef.current = null;
      }
      setElapsedMs(0);

      if (session.intent !== "commit") {
        setStatus("idle");
        setMessage(session.cancelMessage ?? "录音已取消。");
        return;
      }

      const durationMs = Math.max(0, (session.stoppedAt ?? Date.now()) - session.startedAt);
      const blob = new Blob(session.chunks, { type: mimeType || "audio/webm" });

      if (durationMs < MIN_DURATION_MS || durationMs > MAX_DURATION_MS) {
        setStatus("idle");
        setMessage("录音需在 1 到 60 秒之间，请重新录制。");
        return;
      }

      if (blob.size === 0) {
        setStatus("idle");
        setMessage("录制失败，没有生成有效音频，请重试。");
        return;
      }

      if (blob.size > MAX_FILE_BYTES) {
        setStatus("idle");
        setMessage("录音文件超过 5MB，请缩短录音后重试。");
        return;
      }

      const url = URL.createObjectURL(blob);
      replaceClip({
        url,
        blob,
        mimeType: blob.type || mimeType,
        size: blob.size,
        durationMs,
        filename: buildRecordingFilename(blob.type || mimeType),
      });
      setStatus("idle");
      setMessage("录音完成，可以试听或下载文件。");
    },
    [clearSessionTimers, mimeType, replaceClip],
  );

  const start = useCallback(async () => {
    if (sessionRef.current) {
      return;
    }
    if (!supported || !mimeType) {
      setMessage("当前浏览器不支持 WebM/Opus 录音，请更换 Chrome、Edge 或 Firefox。");
      setStatus("idle");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setMessage("当前浏览器无法访问麦克风，请更换 Chrome、Edge 或 Firefox。");
      setStatus("idle");
      return;
    }

    const session = {
      cancelled: false,
      intent: "commit",
      cancelMessage: "录音已取消。",
      chunks: [],
      stream: null,
      recorder: null,
      startedAt: 0,
      stoppedAt: 0,
      maxTimer: 0,
      tick: 0,
    };
    sessionRef.current = session;
    setStatus("requesting");
    setMessage("正在申请麦克风权限…");
    setElapsedMs(0);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (session.cancelled || sessionRef.current !== session) {
        stopTracks(stream);
        return;
      }

      session.stream = stream;
      const recorder = new MediaRecorder(stream, { mimeType });
      session.recorder = recorder;

      recorder.addEventListener("dataavailable", (event) => {
        if (event.data && event.data.size > 0) {
          session.chunks.push(event.data);
        }
      });
      recorder.addEventListener("error", () => {
        session.intent = "discard";
        session.cancelMessage = "录制失败，请重试。";
        if (recorder.state !== "inactive") {
          recorder.stop();
        } else {
          finalizeSession(session);
        }
      });
      recorder.addEventListener("stop", () => {
        session.stoppedAt = Date.now();
        finalizeSession(session);
      });

      recorder.start(250);
      session.startedAt = Date.now();
      setStatus("recording");
      setMessage("录音中，松开结束，Esc 取消。");
      session.tick = window.setInterval(() => {
        setElapsedMs(Date.now() - session.startedAt);
      }, 200);
      session.maxTimer = window.setTimeout(() => {
        if (sessionRef.current !== session) {
          return;
        }
        session.intent = "commit";
        if (recorder.state === "recording") {
          recorder.stop();
        }
      }, MAX_DURATION_MS);
    } catch (error) {
      stopTracks(session.stream);
      if (sessionRef.current === session) {
        sessionRef.current = null;
      }
      setStatus("idle");
      setMessage(describeMediaError(error));
    }
  }, [finalizeSession, mimeType, supported]);

  const stop = useCallback(() => {
    const session = sessionRef.current;
    if (!session) {
      return;
    }
    session.intent = "commit";
    if (!session.recorder) {
      session.cancelled = true;
      session.intent = "discard";
      session.cancelMessage = "录音已取消。";
      stopTracks(session.stream);
      sessionRef.current = null;
      setStatus("idle");
      setMessage("录音已取消。");
      return;
    }
    if (session.recorder.state === "recording") {
      session.recorder.stop();
    }
  }, []);

  const cancel = useCallback(() => {
    const session = sessionRef.current;
    if (!session) {
      return;
    }
    session.cancelled = true;
    session.intent = "discard";
    session.cancelMessage = "录音已取消。";
    if (session.recorder && session.recorder.state !== "inactive") {
      session.recorder.stop();
      return;
    }
    clearSessionTimers(session);
    stopTracks(session.stream);
    sessionRef.current = null;
    setStatus("idle");
    setElapsedMs(0);
    setMessage("录音已取消。");
  }, [clearSessionTimers]);

  useEffect(() => {
    function onPointerUp() {
      if (sessionRef.current) {
        stop();
      }
    }
    function onPointerCancel() {
      if (sessionRef.current) {
        cancel();
      }
    }
    function onKeyDown(event) {
      if (event.key === "Escape" && sessionRef.current) {
        cancel();
      }
    }
    function onVisibilityChange() {
      if (document.hidden && sessionRef.current) {
        stop();
      }
    }

    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerCancel);
    window.addEventListener("keydown", onKeyDown);
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointercancel", onPointerCancel);
      window.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [cancel, stop]);

  useEffect(() => {
    return () => {
      const session = sessionRef.current;
      if (session) {
        session.cancelled = true;
        session.intent = "discard";
        clearSessionTimers(session);
        if (session.recorder && session.recorder.state !== "inactive") {
          try {
            session.recorder.stop();
          } catch {
            stopTracks(session.stream);
          }
        } else {
          stopTracks(session.stream);
        }
        sessionRef.current = null;
      }
      if (clipUrlRef.current) {
        URL.revokeObjectURL(clipUrlRef.current);
        clipUrlRef.current = null;
      }
    };
  }, [clearSessionTimers]);

  return {
    supported,
    mimeType,
    status,
    message,
    elapsedMs,
    clip,
    start,
    stop,
    cancel,
  };
}
