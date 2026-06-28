import { loadIntent } from "@/lib/artifacts";
import { IntakeCard } from "@/components/IntakeCard";

export default function HomePage() {
  const intent = loadIntent();

  return (
    <div className="py-10">
      <section className="mx-auto max-w-6xl px-4 pb-8 text-center">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-cyan">
          Mission control for talent
        </p>
        <h1 className="mt-3 text-balance text-4xl font-bold tracking-tight text-ink sm:text-5xl">
          {intent.job_title}{" "}
          <span className="text-ink-mute">@ {intent.company}</span>
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-pretty text-ink-mute">
          100,000 candidates screened · 201 traps removed · ranked in 73 seconds,
          offline, CPU-only. Drop the JD, run the ranking, see who actually fits.
        </p>
      </section>

      <IntakeCard intent={intent} />
    </div>
  );
}
