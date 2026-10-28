import React, { useEffect, useState } from "react";
import { api } from "../api.js";

// TODO: this is a placeholder. Leadership needs a real dashboard.
export default function Dashboard({ org }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api(`/dashboard?org_id=${org.org_id}`).then(setData).catch((e) => setError(e.message));
  }, [org]);

  if (!data) {
    return (
      <div className="card">
        <h2>Dashboard</h2>
        {error ? <p className="error">{error}</p> : <p>Loading…</p>}
      </div>
    );
  }

  return (
    <div className="card">
      <h2>{data.organization}</h2>
      {data.departments.length === 0 ? (
        <p className="muted">
          No team has five responders yet, so nothing is shown. This is the client's privacy rule.
          Run <code>python -m app.scripts.demo_large_org</code> to add a visible team.
        </p>
      ) : (
        <table>
          <thead>
            <tr><th>Team</th><th>Employees</th><th>Responded</th><th>Average</th><th>Level</th></tr>
          </thead>
          <tbody>
            {data.departments.map((d) => (
              <tr key={d.department}>
                <td>{d.department}</td>
                <td>{d.employees}</td>
                <td>{d.responded}</td>
                <td>{d.average_score ?? "—"}</td>
                <td>{d.level}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <h3>Top risks</h3>
      {data.top_risks.length === 0 ? (
        <p className="muted">No risks above the privacy threshold.</p>
      ) : (
        <ul>
          {data.top_risks.map(([risk, count]) => (
            <li key={risk}>{risk.replaceAll("_", " ")}: {count}</li>
          ))}
        </ul>
      )}
      <p className="muted">
        Teams under five responders are hidden or pooled under "Other teams"; their risks are not counted.
      </p>
    </div>
  );
}
