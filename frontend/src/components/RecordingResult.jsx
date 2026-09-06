import { formatDuration, formatFileSize } from "../audioFormat.js";

export default function RecordingResult({ clip }) {
  if (!clip) {
    return null;
  }

  return (
    <section className="result" aria-label="本地录音">
      <h2>本地试听</h2>
      <audio controls src={clip.url} preload="metadata">
        当前浏览器无法播放这段录音。
      </audio>
      <p className="file-meta">
        格式 {clip.mimeType} · {formatFileSize(clip.size)} · {formatDuration(clip.durationMs)}
      </p>
      <a className="download" href={clip.url} download={clip.filename}>
        下载录音文件
      </a>
      <p className="note">该下载入口仅用于后续独立测试上传接口，本页不会发送录音。</p>
    </section>
  );
}
