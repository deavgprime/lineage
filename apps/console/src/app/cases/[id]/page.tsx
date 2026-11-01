import { notFound } from "next/navigation";

import { api } from "@/lib/api";
import { statusLabel } from "@/lib/format";

import { Header } from "../../header";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ id: string }> };

export default async function CasePage({ params }: Props) {
  const { id } = await params;
  const { data: file } = await (await api(`/cases/${id}`)).GET("/cases/{case_id}", {
    params: { path: { case_id: id } },
  });
  if (!file) notFound();
  return (
    <>
      <Header />
      <main>
        <h1>{file.subject}</h1>
        <p className="muted">
          {file.company_number} · {file.jurisdiction.toUpperCase()} · {statusLabel(file.status)}
        </p>
      </main>
    </>
  );
}
