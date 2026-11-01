import Link from "next/link";

import { api } from "@/lib/api";
import { STATUS_LABELS, age, statusLabel } from "@/lib/format";

import { Header } from "./header";
import { OpenCase } from "./open-case";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ status?: string }> };

export default async function Queue({ searchParams }: Props) {
  const { status } = await searchParams;
  const filter = status && status in STATUS_LABELS ? status : undefined;
  const client = await api();
  const [{ data: me }, { data: cases = [] }] = await Promise.all([
    client.GET("/me"),
    client.GET("/cases", {
      params: { query: filter ? { status: filter as "draft" } : {} },
    }),
  ]);
  const canOpen = me?.role === "analyst" || me?.role === "mlro";
  return (
    <>
      <Header />
      <main>
        <h1>Cases</h1>
        {canOpen && me && <OpenCase packs={me.packs} />}
        <nav className="filters" aria-label="Filter by status">
          <Link href="/" aria-current={!filter ? "page" : undefined}>
            All
          </Link>
          {Object.entries(STATUS_LABELS).map(([key, label]) => (
            <Link key={key} href={`/?status=${key}`} aria-current={filter === key ? "page" : undefined}>
              {label}
            </Link>
          ))}
        </nav>
        {cases.length === 0 ? (
          <p className="muted">No cases{filter ? ` with status ${statusLabel(filter)}` : " yet"}.</p>
        ) : (
          <table className="queue">
            <thead>
              <tr>
                <th>Subject</th>
                <th>Number</th>
                <th>Pack</th>
                <th>Status</th>
                <th>Rating</th>
                <th>Opened</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <td>
                    <Link href={`/cases/${c.id}`}>{c.subject}</Link>
                  </td>
                  <td>{c.company_number ?? ""}</td>
                  <td>{c.jurisdiction.toUpperCase()}</td>
                  <td>{statusLabel(c.status)}</td>
                  <td>{c.rating ? <span className={`rating ${c.rating}`}>{c.rating}</span> : ""}</td>
                  <td>{age(c.created_at)} ago</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </main>
    </>
  );
}
