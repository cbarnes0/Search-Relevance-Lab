"use client";

// The ONLY client component on the page: it holds the input's state and reacts
// to submit. It does NOT fetch — it pushes the query into the URL, and the
// server page re-renders with results (Pattern A). The initial value arrives as
// a prop from the server (data flows server -> client island via props).

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function SearchBox({ initialQuery }: { initialQuery: string }) {
  const router = useRouter();
  const [value, setValue] = useState(initialQuery);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = value.trim();
    router.push(q ? `/?q=${encodeURIComponent(q)}` : "/");
  }

  return (
    <form
      onSubmit={onSubmit}
      style={{ display: "flex", gap: "0.5rem", marginBottom: "2rem" }}
    >
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Search the corpus…"
        style={{
          flex: 1,
          padding: "0.6rem 0.8rem",
          fontSize: "1rem",
          background: "#111",
          color: "#eee",
          border: "1px solid #333",
          borderRadius: "6px",
        }}
      />
      <button
        type="submit"
        style={{
          padding: "0.6rem 1.2rem",
          fontSize: "1rem",
          background: "#2563eb",
          color: "#fff",
          border: "none",
          borderRadius: "6px",
          cursor: "pointer",
        }}
      >
        Search
      </button>
    </form>
  );
}
