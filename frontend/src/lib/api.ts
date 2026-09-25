const API_BASE = "http://localhost:8000/api";

export async function getOrCreateUser() {
  let userId = localStorage.getItem("user_id");
  if (!userId) {
    const res = await fetch(`${API_BASE}/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "Demo User",
        email: `demo_${Date.now()}@example.com`,
        institution: "Hackathon Demo",
      }),
    });
    if (!res.ok) throw new Error("Failed to create user");
    const data = await res.json();
    userId = data.id;
    localStorage.setItem("user_id", userId!);
  }
  return userId;
}

export async function uploadThesis(file: File, title: string) {
  const userId = await getOrCreateUser();
  const formData = new FormData();
  formData.append("file", file);
  formData.append("title", title);
  formData.append("user_id", userId!);

  const res = await fetch(`${API_BASE}/theses`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error("Upload failed");
  return res.json();
}

export async function checkThesisStatus(id: string) {
  const res = await fetch(`${API_BASE}/theses/${id}/status`);
  if (!res.ok) throw new Error("Status check failed");
  return res.json();
}

export async function startSession(thesisId: string, language: string = "en") {
  const userId = await getOrCreateUser();
  const res = await fetch(`${API_BASE}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      thesis_id: thesisId,
      user_id: userId,
      language,
    }),
  });
  if (!res.ok) throw new Error("Failed to start session");
  return res.json();
}

export async function getNextQuestion(sessionId: string) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/next-question`);
  if (!res.ok) {
    if (res.status === 400) {
      const data = await res.json();
      if (data.detail === "All rubric categories have been covered") {
        return { isFinished: true };
      }
    }
    throw new Error("Failed to fetch next question");
  }
  return res.json();
}

export async function submitAnswer(sessionId: string, transcript: string) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/answers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transcript }),
  });
  if (!res.ok) throw new Error("Failed to submit answer");
  return res.json();
}

export async function endSession(sessionId: string) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/end`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to end session");
  return res.json();
}

export async function getReport(sessionId: string) {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/report`);
  if (!res.ok) throw new Error("Failed to fetch report");
  return res.json();
}
