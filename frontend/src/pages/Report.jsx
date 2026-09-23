import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Report() {
  const [report, setReport] = useState(null);

  useEffect(() => {
    api("/reports/me").then(setReport);
  }, []);

  if (!report) return <p>Loading…</p>;
  return (
    <div className="card">
      <h2>{report.name}: {report.level}</h2>
      <p>Average score: {report.average_score}</p>
      <h3>Risks</h3>
      <ul>{report.risks.map((r) => <li key={r}>{r}</li>)}</ul>
      <h3>Next steps</h3>
      <ul>{report.next_steps.map((s) => <li key={s}>{s}</li>)}</ul>
    </div>
  );
}
