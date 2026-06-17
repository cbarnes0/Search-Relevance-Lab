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
        style={{ flex: 1 }}
      />
      <button type="submit">Search</button>
    </form>
  );
}
