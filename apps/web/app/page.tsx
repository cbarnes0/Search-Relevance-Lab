type HealthResponse = {
  status: "healthy" | "degraded";
  backends: {
    postgres: boolean;
    typesense: boolean;
    qdrant: boolean;
  };
};

async function getHealth(): Promise<HealthResponse | null> {
  const apiUrl = process.env.API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/health`, { cache: "no-store" });
    return res.json();
  } catch {
    return null;
  }
}

function StatusBadge({ ok }: { ok: boolean }) {
  return (
    <span style={{ color: ok ? "#4ade80" : "#f87171" }}>
      {ok ? "healthy" : "unreachable"}
    </span>
  );
}

export default async function Page() {
  const health = await getHealth();

  return (
    <main style={{ padding: "2rem", maxWidth: "480px", margin: "4rem auto" }}>
      <h1 style={{ marginBottom: "0.5rem" }}>Search Relevance Lab</h1>
      <p style={{ color: "#888", marginBottom: "2rem" }}>Backend status</p>

      {health === null ? (
        <p style={{ color: "#f87171" }}>Could not reach API</p>
      ) : (
        <>
          <p style={{ marginBottom: "1.5rem" }}>
            API:{" "}
            <span style={{ color: health.status === "healthy" ? "#4ade80" : "#f87171" }}>
              {health.status}
            </span>
          </p>
          <table style={{ borderCollapse: "collapse", width: "100%" }}>
            <tbody>
              {Object.entries(health.backends).map(([name, ok]) => (
                <tr key={name} style={{ borderBottom: "1px solid #222" }}>
                  <td style={{ padding: "0.75rem 0", textTransform: "capitalize" }}>{name}</td>
                  <td style={{ padding: "0.75rem 0", textAlign: "right" }}>
                    <StatusBadge ok={ok} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </main>
  );
}
