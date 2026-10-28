import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Diagnostic({ onDone }) {
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [error, setError] = useState("");

  useEffect(() => {
    api("/diagnostic/questions").then(setQuestions).catch((e) => setError(e.message));
  }, []);

  async function submit() {
    const payload = Object.entries(answers).map(([question_id, answer]) => ({ question_id, answer }));
    try {
      await api("/diagnostic/submit", { method: "POST", body: JSON.stringify({ answers: payload }) });
      onDone();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="card">
      <h2>Your AI diagnostic</h2>
      {error && <p className="error">{error}</p>}
      {questions.map((q) => (
        <div key={q.id}>
          <p><b>{q.text}</b></p>
          {q.type === "mcq" ? (
            <select onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })} defaultValue="">
              <option value="" disabled>Choose…</option>
              {q.options.map((o) => <option key={o}>{o}</option>)}
            </select>
          ) : (
            <textarea rows={4} onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })} />
          )}
        </div>
      ))}
      <button onClick={submit}>Submit</button>
    </div>
  );
}
