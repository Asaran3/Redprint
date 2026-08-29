"use client";

import { FormEvent, useMemo, useState } from "react";

type FindingStatus =
  | "COMPLIANT"
  | "NONCOMPLIANT"
  | "INSUFFICIENT_EVIDENCE"
  | "NOT_APPLICABLE";

type OverallStatus = "PASS" | "FAIL" | "MIXED" | "INSUFFICIENT_EVIDENCE";

type ComplianceReport = {
  filename: string;
  overall_status: OverallStatus;
  executive_summary: string;
  jurisdiction: {
    city: string;
    county: string;
    state: string;
    postal_code: string;
    display_name?: string | null;
  };
  findings: {
    category: string;
    status: FindingStatus;
    title: string;
    observation: string;
    code_citation: string;
    code_excerpt: string;
    recommendation: string;
    sheet_hint: string;
  }[];
  coverage: {
    pages_reviewed: number;
    code_chunks_used: number;
    jurisdiction_filter: string;
    notes: string;
  };
};

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

const overallLabel: Record<OverallStatus, string> = {
  PASS: "Complying",
  FAIL: "Noncompliant items found",
  MIXED: "Mixed — some issues",
  INSUFFICIENT_EVIDENCE: "Incomplete evidence",
};

function statusClass(status: string) {
  switch (status) {
    case "PASS":
    case "COMPLIANT":
      return "bg-emerald-100 text-emerald-900";
    case "FAIL":
    case "NONCOMPLIANT":
      return "bg-red-100 text-red-900";
    case "MIXED":
      return "bg-amber-100 text-amber-900";
    default:
      return "bg-zinc-200 text-zinc-800";
  }
}

export default function HomeClient() {
  const [address, setAddress] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ComplianceReport | null>(null);

  const counts = useMemo(() => {
    if (!report) return null;
    return report.findings.reduce(
      (acc, finding) => {
        acc[finding.status] += 1;
        return acc;
      },
      {
        COMPLIANT: 0,
        NONCOMPLIANT: 0,
        INSUFFICIENT_EVIDENCE: 0,
        NOT_APPLICABLE: 0,
      } as Record<FindingStatus, number>,
    );
  }, [report]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setReport(null);

    if (!address.trim() || !file) {
      setError("Enter a property address and upload a PDF blueprint.");
      return;
    }

    const body = new FormData();
    body.append("address", address.trim());
    body.append("blueprint", file);

    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/analyze`, {
        method: "POST",
        body,
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        const detail =
          typeof payload?.detail === "string"
            ? payload.detail
            : "Analysis failed. Check that the API is running.";
        throw new Error(detail);
      }
      setReport(payload as ComplianceReport);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-full bg-zinc-50 text-zinc-950">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto max-w-5xl px-6 py-5">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-zinc-500">
            Redprint
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">
            Blueprint compliance report
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-zinc-600">
            Submit an address and plan set. The review covers the whole drawing,
            not a single question.
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        <form onSubmit={onSubmit} className="space-y-4 rounded-lg border border-zinc-200 bg-white p-5">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-zinc-700">
              Property address
            </span>
            <input
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="Sunnyvale, CA"
              className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 outline-none focus:border-zinc-900"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-zinc-700">
              Blueprint PDF
            </span>
            <input
              type="file"
              accept="application/pdf"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-zinc-900 file:px-3 file:py-2 file:text-white"
            />
          </label>
          <button
            type="submit"
            disabled={loading}
            className="h-10 rounded-md bg-zinc-900 px-5 text-sm font-medium text-white disabled:opacity-60"
          >
            {loading ? "Reviewing plans…" : "Generate report"}
          </button>
        </form>

        {error ? (
          <p className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            {error}
          </p>
        ) : null}

        {loading ? (
          <p className="mt-6 text-sm text-zinc-600">
            Resolving jurisdiction, reading sheets, and checking municipal
            code. This can take a minute.
          </p>
        ) : null}

        {report ? (
          <section className="mt-8 space-y-6">
            <div className="rounded-lg border border-zinc-200 bg-white p-5">
              <div className="flex flex-wrap items-center gap-3">
                <span
                  className={`rounded-full px-3 py-1 text-sm font-medium ${statusClass(report.overall_status)}`}
                >
                  {overallLabel[report.overall_status]}
                </span>
                <p className="text-sm text-zinc-600">
                  {report.jurisdiction.display_name ||
                    `${report.jurisdiction.city}, ${report.jurisdiction.state}`}
                </p>
              </div>
              <p className="mt-4 text-[15px] leading-7 text-zinc-800">
                {report.executive_summary}
              </p>
              {counts ? (
                <p className="mt-4 text-sm text-zinc-500">
                  {counts.NONCOMPLIANT} noncompliant · {counts.COMPLIANT}{" "}
                  complying · {counts.INSUFFICIENT_EVIDENCE} not enough on
                  drawings · {report.coverage.pages_reviewed} sheets reviewed
                </p>
              ) : null}
            </div>

            <ul className="space-y-3">
              {report.findings.map((finding, index) => (
                <li
                  key={`${finding.title}-${index}`}
                  className="rounded-lg border border-zinc-200 bg-white p-5"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${statusClass(finding.status)}`}
                    >
                      {finding.status.replaceAll("_", " ")}
                    </span>
                    <span className="text-xs uppercase tracking-wide text-zinc-500">
                      {finding.category}
                    </span>
                    {finding.sheet_hint ? (
                      <span className="text-xs text-zinc-400">
                        {finding.sheet_hint}
                      </span>
                    ) : null}
                  </div>
                  <h2 className="mt-2 text-lg font-medium">{finding.title}</h2>
                  <p className="mt-2 text-sm leading-6 text-zinc-700">
                    {finding.observation}
                  </p>
                  {finding.code_citation ? (
                    <p className="mt-3 text-sm text-zinc-600">
                      <span className="font-medium text-zinc-900">Code. </span>
                      {finding.code_citation}
                      {finding.code_excerpt ? ` — ${finding.code_excerpt}` : ""}
                    </p>
                  ) : null}
                  {finding.recommendation ? (
                    <p className="mt-2 text-sm text-zinc-600">
                      <span className="font-medium text-zinc-900">
                        Next step.{" "}
                      </span>
                      {finding.recommendation}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>

            {report.coverage.notes ? (
              <p className="text-sm leading-6 text-zinc-500">
                Coverage: {report.coverage.notes}
              </p>
            ) : null}
          </section>
        ) : null}
      </main>
    </div>
  );
}
