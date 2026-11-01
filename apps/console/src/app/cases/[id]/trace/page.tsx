import Link from "next/link";
import { notFound } from "next/navigation";

import { api } from "@/lib/api";
import { chainStatus, describe } from "@/lib/trace";

import { Header } from "../../../header";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ id: string }> };

export default async function TracePage({ params }: Props) {
  const { id } = await params;
  const client = await api(`/cases/${id}/trace`);
  const [{ data: file }, { data: rows }] = await Promise.all([
    client.GET("/cases/{case_id}", { params: { path: { case_id: id } } }),
    client.GET("/cases/{case_id}/audit", { params: { path: { case_id: id } } }),
  ]);
  if (!file || !rows) notFound();
  const chain = chainStatus(rows);
  // Users appear in the log by id; show the names this file already knows.
  const names = new Map(file.sign_offs.map((s) => [s.signer, s.signer_name]));
  return (
    <>
      <Header />
      <main>
        <p>
          <Link href={`/cases/${id}`}>Back to the file</Link>
        </p>
        <h1>How {file.subject} was drafted</h1>
        <p className={chain.ok ? "chain ok" : "chain broken"}>
          {chain.ok
            ? `All ${rows.length} audit rows verify against the hash chain.`
            : `The hash chain is broken at row ${chain.firstBroken}. Rows from there on may have been changed.`}
        </p>
        <ol className="trace">
          {rows.map((r) => (
            <li key={r.seq} className={r.verified ? undefined : "broken"}>
              <time dateTime={r.at}>{new Date(r.at).toISOString().slice(11, 19)}</time>
              <span className="actor">{r.actor === "agent" ? "agent" : (names.get(r.actor) ?? "user")}</span>
              <span>{describe(r.action, r.payload)}</span>
              <span className="mono muted" title={r.row_hash}>
                {r.row_hash.slice(0, 12)}
                {r.verified ? "" : " ✗"}
              </span>
            </li>
          ))}
        </ol>
      </main>
    </>
  );
}
