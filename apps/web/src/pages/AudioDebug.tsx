import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { readAudioReport, type AudioReport } from "../features/voice/diagnostics";

const phases: Record<string, string> = { permission: "等待授权", recording: "正在收音", recognizing: "语音识别中", recognized: "识别完成", thinking: "处理请求中", speaking: "正在播报", done: "已完成", stopped: "已停止", error: "失败" };
export function AudioDebugPage() {
  const read = () => [readAudioReport("assistant"), readAudioReport("coach")];
  const [reports, setReports] = useState(read);
  useEffect(() => {
    const update = () => setReports(read());
    window.addEventListener("xiaoban-audio-report", update);
    return () => window.removeEventListener("xiaoban-audio-report", update);
  }, []);
  function panel(title: string, report: AudioReport | null) {
    return <section className="panel" key={title}>
      <h2>{title}</h2>
      <dl>
        <div><dt>最近阶段</dt><dd>{report ? phases[report.phase] || report.phase : "尚未测试"}</dd></div>
        <div><dt>录音采样数</dt><dd>{report?.samples || 0}</dd></div>
        <div><dt>输入峰值</dt><dd>{report?.peak?.toPrecision(4) || "0"}</dd></div>
        <div><dt>实际输入设备</dt><dd>{report?.device || "—"}</dd></div>
        {report?.avoidedDevice && <div><dt>已避开虚拟输入</dt><dd>{report.avoidedDevice}</dd></div>}
        <div><dt>输入声道</dt><dd>{report?.channels ?? "—"}</dd></div>
        <div><dt>输入处理</dt><dd>{report?.inputMode || "—"}</dd></div>
        <div><dt>识别字数</dt><dd>{report?.characters || 0}</dd></div>
        <div><dt>录音引擎</dt><dd>{report?.engine || "—"}</dd></div>
        <div><dt>错误代码</dt><dd>{report?.code || "无"}</dd></div>
      </dl>
    </section>;
  }
  return <div className="page audio-debug" data-page="home">
    <h1>收音诊断</h1>
    <p>底部麦克风测试助手；陪练页的开始按钮测试陪练。测试后可回到此页查看。</p>
    <p>此页只显示阶段、音量和字数，不保存录音或对话文字。</p>
    <div className="audio-debug-links"><Link to="/">首页</Link><Link to="/practice?mode=voice">语音陪练</Link></div>
    {panel("语音助手", reports[0])}{panel("语音陪练", reports[1])}
  </div>;
}
