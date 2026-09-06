import { useState } from "react";

import CitySelect from "./components/CitySelect.jsx";
import RecordButton from "./components/RecordButton.jsx";
import RecordingResult from "./components/RecordingResult.jsx";
import { useRecorder } from "./useRecorder.js";

export default function App() {
  const [city, setCity] = useState("杭州");
  const recorder = useRecorder();

  return (
    <main className="page">
      <section className="card">
        <p className="eyebrow">第一版 · 同城两人</p>
        <h1>语音约碰面地点</h1>
        <p className="lead">
          按住按钮说出两个人各自所在的地点。本轮只完成本地录音，不会识别或找店。
        </p>

        <CitySelect value={city} onChange={setCity} />

        <RecordButton
          supported={recorder.supported}
          status={recorder.status}
          elapsedMs={recorder.elapsedMs}
          onHoldStart={recorder.start}
        />

        {recorder.message ? (
          <p className="status" role="status">
            {recorder.message}
          </p>
        ) : null}

        <RecordingResult clip={recorder.clip} />
      </section>
    </main>
  );
}
