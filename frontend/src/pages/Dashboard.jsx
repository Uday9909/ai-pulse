import React, { useEffect, useState } from "react";
import { api } from "../api.js";

// TODO: this is a placeholder. Leadership needs a real dashboard.
export default function Dashboard({ org }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api(`/dashboard?org_id=${org.org_id}`).then(setData).catch((e) => setError(e.message));
  }, [org]);

  return (
    <div className="card">
      <h2>Dashboard</h2>
      {error && <p className="error">{error}</p>}
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}
