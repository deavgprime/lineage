import Link from "next/link";

import { api } from "@/lib/api";

export async function Header() {
  const { data: me } = await (await api()).GET("/me");
  return (
    <header className="top">
      <Link className="brand" href="/">
        Lineage
      </Link>
      {me && (
        <div className="who">
          <span>
            {me.username} · {me.role} · {me.packs.map((p) => p.toUpperCase()).join(", ")}
          </span>
          <form action="/auth/logout" method="post">
            <button type="submit">Sign out</button>
          </form>
        </div>
      )}
    </header>
  );
}
