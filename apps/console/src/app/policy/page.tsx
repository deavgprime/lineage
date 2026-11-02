import Link from "next/link";

import { api } from "@/lib/api";
import { locate } from "@/lib/quote";

import { Header } from "../header";
import { AskForm } from "./ask-form";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ q?: string; cite?: string }> };

export default async function PolicyPage({ searchParams }: Props) {
  const { q, cite } = await searchParams;
  const client = await api("/policy");
  const [{ data: me }, { data: history = [] }] = await Promise.all([
    client.GET("/me"),
    client.GET("/policy/questions"),
  ]);
  const current = q
    ? (await client.GET("/policy/questions/{question_id}", { params: { path: { question_id: q } } })).data
    : undefined;
  const statement = current && cite !== undefined ? current.statements[Number(cite)] : undefined;
  const passage = statement ? current?.passages.find((p) => p.id === statement.source_id) : undefined;
  const parts = passage && statement ? locate(passage.text, statement.quote) : null;

  return (
    <>
      <Header />
      <main className="file">
        <p>
          <Link href="/">Cases</Link>
        </p>
        <h1>Policy questions</h1>
        <p className="muted">
          Answers come only from the bank&apos;s KYC policy and the regulations loaded for your pack. Every statement
          links to the passage it rests on.
        </p>
        {me && <AskForm packs={me.packs} />}

        {current && (
          <div className="columns">
            <section className="panel">
              <h2>{current.question}</h2>
              <p className="muted">
                {current.pack.toUpperCase()} · asked by {current.asked_by_name}
              </p>
              {current.answered ? (
                <ul className="claims">
                  {current.statements.map((s, i) => (
                    <li key={i} className={cite === String(i) ? "active" : undefined}>
                      {s.text}{" "}
                      <Link className="cite" href={`/policy?q=${current.id}&cite=${i}`} scroll={false}>
                        source
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>{current.note || "The policy passages found do not answer this question."}</p>
              )}
              {current.citation_failures.length > 0 && (
                <p className="error">The answer could not be fully cited, so it is not shown.</p>
              )}
            </section>
            <aside className="panel source" aria-live="polite">
              {passage && statement ? (
                <>
                  <h2>
                    {passage.ref}: {passage.heading}
                  </h2>
                  <p className="muted">{passage.document}</p>
                  <p className="record">
                    {parts ? (
                      <>
                        {parts[0]}
                        <mark>{parts[1]}</mark>
                        {parts[2]}
                      </>
                    ) : (
                      passage.text
                    )}
                  </p>
                </>
              ) : (
                <p className="muted">Choose a source next to any statement to see the passage it quotes.</p>
              )}
            </aside>
          </div>
        )}

        {history.length > 0 && (
          <section className="panel history">
            <h2>Recent questions</h2>
            <ul>
              {history.map((h) => (
                <li key={h.id}>
                  <Link href={`/policy?q=${h.id}`}>{h.question}</Link>{" "}
                  <span className="muted">
                    {h.pack.toUpperCase()} · {h.asked_by_name} · {new Date(h.at).toISOString().slice(0, 16).replace("T", " ")} UTC
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
    </>
  );
}
