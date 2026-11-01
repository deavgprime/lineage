import { Header } from "./header";

export const dynamic = "force-dynamic";

export default async function Home() {
  return (
    <>
      <Header />
      <main>
        <h1>Cases</h1>
        <p className="muted">No cases yet.</p>
      </main>
    </>
  );
}
