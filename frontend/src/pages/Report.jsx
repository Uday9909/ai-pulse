import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Report() {
  const [report, setReport] = useState(null);

  function load() {
    return api("/reports/me").then(setReport);
  }

  useEffect(() => {
    load();
  }, []);

  async function remove() {
    if (!window.confirm("Delete all your answers for this organization?")) return;
    await api("/reports/me", { method: "DELETE" });
    await load();
  }

  if (!report) return <p>Loading…</p>;
  return (
    <div className="card">
      <h2>{report.name}: {report.level}</h2>
      <p>Average score: {report.average_score}</p>
      <h3>Your answers</h3>
      <ul>
        {report.answers.map((a, i) => (
          <li key={`${a.question_id}-${i}`}>
            <b>{a.question_id}</b>: {a.score ?? "not scored"}
            {a.reason && <span> — {a.reason}</span>}
          </li>
        ))}
      </ul>
      <h3>Risks</h3>
      <ul>{report.risks.map((r) => <li key={r}>{r}</li>)}</ul>
      <h3>Next steps</h3>
      <ul>{report.next_steps.map((s) => <li key={s}>{s}</li>)}</ul>
      <button onClick={remove}>Delete my answers</button>
    </div>
  );
}
