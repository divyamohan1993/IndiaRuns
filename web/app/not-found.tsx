import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center px-4 py-24 text-center">
      <p className="font-mono text-xs uppercase tracking-[0.3em] text-cyan">
        404
      </p>
      <h1 className="mt-3 text-3xl font-bold text-ink">Out of band</h1>
      <p className="mt-2 text-ink-mute">
        That candidate rank or route isn&apos;t in the shortlist.
      </p>
      <Link
        href="/board"
        className="mt-6 rounded-xl bg-gold px-5 py-3 font-semibold text-navy-900"
      >
        Back to the board →
      </Link>
    </div>
  );
}
