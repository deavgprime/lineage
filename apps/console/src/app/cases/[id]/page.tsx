import Link from "next/link";
import { notFound } from "next/navigation";

import { api } from "@/lib/api";
import { statusLabel } from "@/lib/format";
import { locate } from "@/lib/quote";

import { Header } from "../../header";
import { SignOffForm } from "./sign-off-form";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ id: string }>; searchParams: Promise<{ cite?: string }> };

type Claim = { text: string; source_id: string; quote: string };
type Draft = {
  summary: Claim[];
  ownership: Claim[];
  screening: Claim[];
  adverse_media?: Claim[];
  flags?: Claim[];
  risk_rating: string;
  risk_reasons: Claim[];
};

const SECTIONS: [keyof Draft, string][] = [
  ["summary", "Summary"],
  ["ownership", "Ownership"],
  ["screening", "Screening"],
  ["adverse_media", "Adverse media"],
  ["risk_reasons", "Risk rating reasons"],
];

export default async function CasePage({ params, searchParams }: Props) {
  const { id } = await params;
  const { cite } = await searchParams;
  const client = await api(`/cases/${id}`);
  const [{ data: file }, { data: me }] = await Promise.all([
    client.GET("/cases/{case_id}", { params: { path: { case_id: id } } }),
    client.GET("/me"),
  ]);
  if (!file || !me) notFound();
  // Which sign-off, if any, this user can give now. The API checks the same rules again.
  const first = file.sign_offs.find((s) => s.stage === "first");
  const stage =
    file.status === "draft" && (me.role === "mlro" || (me.role === "analyst" && file.assigned_to === me.id))
      ? "first"
      : file.status === "awaiting_mlro" && me.role === "mlro" && first?.signer !== me.id
        ? "second"
        : null;
  const draft = file.draft as Draft | null;
  const evidence = new Map(file.evidence.map((e) => [e.source_id ?? "", e]));
  // The cited claim, as "section.index", whose quote is shown in its record.
  const [citedSection, citedIndex] = (cite ?? "").split(".");
  const cited = draft?.[citedSection as keyof Draft];
  const citedClaim = Array.isArray(cited) ? cited[Number(citedIndex)] : undefined;
  const record = citedClaim ? evidence.get(citedClaim.source_id) : undefined;
  const parts = record && citedClaim ? locate(record.text ?? "", citedClaim.quote) : null;

  return (
    <>
      <Header />
      <main className="file">
        <p>
          <Link href="/">Cases</Link> · <Link href={`/cases/${id}/trace`}>Trace</Link>
        </p>
        <h1>{file.subject}</h1>
        <p className="muted">
          {file.company_number} · {file.jurisdiction.toUpperCase()} · {statusLabel(file.status)}
          {file.attempts ? ` · drafted in ${file.attempts} attempt${file.attempts > 1 ? "s" : ""}` : ""}
        </p>

        {!draft && <p className="panel">{file.status === "drafting" ? "The agent is still drafting this file. Refresh in a moment." : "There is no draft for this case."}</p>}

        {draft && (
          <div className="columns">
            <div>
              <section className="panel rating-box">
                <h2>
                  Rating: <span className={`rating ${file.rating ?? draft.risk_rating}`}>{file.rating ?? draft.risk_rating}</span>
                </h2>
                {file.minimum_rating && file.minimum_rating !== "low" && (
                  <p>
                    A strong screening match sets the minimum rating to <strong>{file.minimum_rating}</strong>. The
                    agent cannot rate it lower.
                  </p>
                )}
              </section>

              {(draft.flags?.length ?? 0) > 0 && (
                <section className="panel flags">
                  <h2>Instructions found in the evidence</h2>
                  <p className="muted">The agent did not follow these. Check the source before signing off.</p>
                  <Claims claims={draft.flags ?? []} section="flags" id={id} active={cite} />
                </section>
              )}

              {file.alerts.length > 0 && (
                <section className="panel alerts">
                  <h2>Alerts to clear</h2>
                  <p className="muted">
                    Weak screening matches. They do not change the rating, but each needs a note before sign-off.
                  </p>
                  <ul>
                    {file.alerts.map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                </section>
              )}

              {file.sign_offs.length > 0 && (
                <section className="panel">
                  <h2>Sign-offs</h2>
                  <ul className="sign-offs">
                    {file.sign_offs.map((s) => (
                      <li key={s.stage}>
                        <strong>{s.stage === "first" ? "First" : "Second"}</strong>: {s.signer_name} ({s.role}),{" "}
                        {new Date(s.at).toLocaleString("en-GB", { timeZone: "UTC" })} UTC. Rated {s.rating}
                        {s.rating !== s.drafted_rating ? `, changed from ${s.drafted_rating}` : ""}.
                        {s.reason && <span className="muted"> {s.reason}</span>}
                      </li>
                    ))}
                  </ul>
                  {file.status === "awaiting_mlro" && !stage && (
                    <p className="muted">Waiting for a second sign-off by a different MLRO.</p>
                  )}
                </section>
              )}

              {stage && draft && (
                <SignOffForm
                  caseId={id}
                  stage={stage}
                  basis={stage === "first" ? draft.risk_rating : (first?.rating ?? draft.risk_rating)}
                  minimum={file.minimum_rating}
                  alerts={file.alerts}
                />
              )}

              {SECTIONS.map(([key, title]) => {
                const claims = draft[key];
                if (!Array.isArray(claims) || claims.length === 0) return null;
                return (
                  <section key={key} className="panel">
                    <h2>{title}</h2>
                    <Claims claims={claims} section={key} id={id} active={cite} />
                  </section>
                );
              })}
            </div>

            <aside className="panel source" aria-live="polite">
              {record && citedClaim ? (
                <>
                  <h2>{record.title}</h2>
                  <p className="muted mono">{record.source_id}</p>
                  <p className="record">
                    {parts ? (
                      <>
                        {parts[0]}
                        <mark>{parts[1]}</mark>
                        {parts[2]}
                      </>
                    ) : (
                      record.text
                    )}
                  </p>
                  {!parts && <p className="error">The quoted passage was not found in this record.</p>}
                </>
              ) : (
                <p className="muted">Choose a source next to any claim to see the passage it quotes.</p>
              )}
            </aside>
          </div>
        )}
      </main>
    </>
  );
}

function Claims({ claims, section, id, active }: { claims: Claim[]; section: string; id: string; active?: string }) {
  return (
    <ul className="claims">
      {claims.map((c, i) => {
        const key = `${section}.${i}`;
        return (
          <li key={key} className={active === key ? "active" : undefined}>
            {c.text}{" "}
            <Link className="cite" href={`/cases/${id}?cite=${key}`} scroll={false}>
              source
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
