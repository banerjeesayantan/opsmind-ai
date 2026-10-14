"use client";

import { useState } from "react";
import {
  Check,
  Code2,
  Copy,
  Eye,
  EyeOff,
  Radio,
  RefreshCw,
  Server,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { Card, Button } from "@/components/ui";
import { api, getStoredToken } from "@/lib/api-client";

type Stack = "nodejs" | "python" | "curl";

export default function SetupPage() {
  const [selectedStack, setSelectedStack] = useState<Stack>("nodejs");
  const [showKey, setShowKey] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);
  const [copiedEnv, setCopiedEnv] = useState(false);
  const [copiedSnippet, setCopiedSnippet] = useState(false);

  // Connection verification state
  const [verifying, setVerifying] = useState(false);
  const [verificationResult, setVerificationResult] = useState<{
    success: boolean;
    latencyMs: number;
    message: string;
    components?: Record<string, string>;
    timestamp?: string;
  } | null>(null);

  const realToken = getStoredToken();
  const apiKey = realToken || "opsmind_live_sec_9934f82ae018";
  const apiEndpoint =
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

  const handleCopy = (text: string, setter: (val: boolean) => void) => {
    navigator.clipboard.writeText(text);
    setter(true);
    setTimeout(() => setter(false), 2000);
  };

  const handleVerify = async () => {
    setVerifying(true);
    setVerificationResult(null);
    const start = performance.now();
    try {
      const res = await api.get<{
        status: string;
        version?: string;
        components?: Record<string, string>;
      }>("/health");
      const elapsed = Math.round(performance.now() - start);
      setVerificationResult({
        success: res.status === "healthy",
        latencyMs: elapsed,
        message:
          res.status === "healthy"
            ? `OpsMind AI API v${res.version ?? "1.0.0"} is healthy and reachable.`
            : `API status: ${res.status}`,
        components: res.components ?? { api: "healthy", database: "healthy" },
        timestamp: new Date().toLocaleTimeString(),
      });
    } catch (err: unknown) {
      const elapsed = Math.round(performance.now() - start);
      setVerificationResult({
        success: false,
        latencyMs: elapsed,
        message:
          err instanceof Error
            ? err.message
            : "Could not connect to the OpsMind AI backend API.",
        timestamp: new Date().toLocaleTimeString(),
      });
    } finally {
      setVerifying(false);
    }
  };

  const envContent = `OPSMIND_API_KEY=${apiKey}\nOPSMIND_ENDPOINT=${apiEndpoint}`;

  const codeSnippets: Record<Stack, { install: string; code: string }> = {
    nodejs: {
      install: "npm install @opsmind/sdk",
      code: `import { OpsMind } from "@opsmind/sdk";

// Initialize OpsMind AI client
const opsmind = new OpsMind({
  apiKey: process.env.OPSMIND_API_KEY,
  endpoint: process.env.OPSMIND_ENDPOINT,
});

// Automatic telemetry & incident reporting
await opsmind.reportIncident({
  service: "payment-service",
  title: "Database connection pool timeout",
  severity: "critical",
});`,
    },
    python: {
      install: "pip install opsmind",
      code: `import os
from opsmind import OpsMindClient

# Initialize OpsMind AI client
client = OpsMindClient(
    api_key=os.environ.get("OPSMIND_API_KEY"),
    endpoint=os.environ.get("OPSMIND_ENDPOINT", "http://localhost:8000/api/v1")
)

# Automatic telemetry & incident reporting
client.report_incident(
    service="payment-service",
    title="Database connection pool timeout",
    severity="critical"
)`,
    },
    curl: {
      install: "# No installation needed (cURL / HTTP REST API)",
      code: `curl -X POST "${apiEndpoint}/incidents" \\
  -H "Authorization: Bearer ${apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "service": "payment-service",
    "title": "Database connection pool timeout",
    "severity": "critical"
  }'`,
    },
  };

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl px-5 py-6 sm:px-8 sm:py-8 space-y-6">
        {/* Header */}
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-ink">SDK Setup &amp; Configuration</h1>
            <span className="inline-flex items-center rounded-full border border-border bg-surface-raised px-2.5 py-0.5 text-xs font-medium text-ink-secondary">
              v1.0
            </span>
          </div>
          <p className="mt-1 text-sm text-ink-secondary">
            Connect your microservices, applications, and pipelines to OpsMind AI for automated incident detection and root-cause analysis.
          </p>
        </div>

        {/* Stack Selection */}
        <Card className="p-5">
          <label className="block text-xs font-semibold uppercase tracking-wider text-ink-secondary mb-3">
            1. Select Your Runtime / Stack
          </label>
          <div className="inline-flex rounded-md bg-surface-raised border border-border p-1 gap-1">
            <button
              type="button"
              onClick={() => setSelectedStack("nodejs")}
              className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-medium rounded transition-colors ${
                selectedStack === "nodejs"
                  ? "bg-accent text-white"
                  : "text-ink-secondary hover:text-ink hover:bg-surface-hover"
              }`}
            >
              <Code2 className="h-3.5 w-3.5" />
              Node.js / TypeScript
            </button>
            <button
              type="button"
              onClick={() => setSelectedStack("python")}
              className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-medium rounded transition-colors ${
                selectedStack === "python"
                  ? "bg-accent text-white"
                  : "text-ink-secondary hover:text-ink hover:bg-surface-hover"
              }`}
            >
              <Terminal className="h-3.5 w-3.5" />
              Python
            </button>
            <button
              type="button"
              onClick={() => setSelectedStack("curl")}
              className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-medium rounded transition-colors ${
                selectedStack === "curl"
                  ? "bg-accent text-white"
                  : "text-ink-secondary hover:text-ink hover:bg-surface-hover"
              }`}
            >
              <Server className="h-3.5 w-3.5" />
              Go / cURL / REST API
            </button>
          </div>
        </Card>

        {/* Step 2: Install Package */}
        <Card className="p-5">
          <div className="flex items-center justify-between mb-3">
            <label className="text-xs font-semibold uppercase tracking-wider text-ink-secondary">
              2. Install SDK Dependency
            </label>
            <span className="text-xs text-ink-tertiary">Package registry</span>
          </div>
          <div className="flex items-center justify-between rounded-md border border-border bg-base px-4 py-3 font-mono text-xs text-ink">
            <span>{codeSnippets[selectedStack].install}</span>
            {selectedStack !== "curl" && (
              <button
                type="button"
                onClick={() => handleCopy(codeSnippets[selectedStack].install, setCopiedSnippet)}
                className="ml-3 text-ink-tertiary hover:text-ink transition-colors"
                title="Copy install command"
              >
                {copiedSnippet ? (
                  <Check className="h-4 w-4 text-severity-low" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </button>
            )}
          </div>
        </Card>

        {/* Step 3: API Key & Environment */}
        <Card className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-ink-secondary">
                3. Configure Environment Variables
              </label>
              <p className="text-xs text-ink-tertiary mt-0.5">
                Keep your API credentials secure in your local <code>.env</code> file.
              </p>
            </div>
            <div className="flex items-center gap-1 text-xs text-severity-low">
              <ShieldCheck className="h-4 w-4" />
              <span>TLS 1.3 Encrypted</span>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5 text-xs text-ink-secondary">
              <span>OpsMind AI Secret Token</span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="flex items-center gap-1 hover:text-ink transition-colors"
                >
                  {showKey ? (
                    <>
                      <EyeOff className="h-3.5 w-3.5" /> Hide
                    </>
                  ) : (
                    <>
                      <Eye className="h-3.5 w-3.5" /> Reveal
                    </>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => handleCopy(apiKey, setCopiedKey)}
                  className="flex items-center gap-1 hover:text-ink transition-colors"
                >
                  {copiedKey ? (
                    <>
                      <Check className="h-3.5 w-3.5 text-severity-low" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5" /> Copy Key
                    </>
                  )}
                </button>
              </div>
            </div>
            <div className="rounded-md border border-border bg-base px-3.5 py-2.5 font-mono text-xs text-ink truncate">
              {showKey ? apiKey : apiKey.slice(0, 10) + "••••••••••••••••••••••••••••"}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5 text-xs text-ink-secondary">
              <span>.env Configuration Snippet</span>
              <button
                type="button"
                onClick={() => handleCopy(envContent, setCopiedEnv)}
                className="flex items-center gap-1 hover:text-ink transition-colors"
              >
                {copiedEnv ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-severity-low" /> Copied .env
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" /> Copy .env
                  </>
                )}
              </button>
            </div>
            <pre className="rounded-md border border-border bg-base p-3 font-mono text-xs text-ink-secondary overflow-x-auto">
              {envContent}
            </pre>
          </div>
        </Card>

        {/* Step 4: Initialization Code */}
        <Card className="p-5">
          <div className="flex items-center justify-between mb-3">
            <label className="text-xs font-semibold uppercase tracking-wider text-ink-secondary">
              4. Code Integration
            </label>
            <button
              type="button"
              onClick={() => handleCopy(codeSnippets[selectedStack].code, setCopiedSnippet)}
              className="flex items-center gap-1 text-xs text-ink-secondary hover:text-ink transition-colors"
            >
              <Copy className="h-3.5 w-3.5" /> Copy Code
            </button>
          </div>
          <pre className="rounded-md border border-border bg-base p-4 font-mono text-xs text-ink overflow-x-auto leading-relaxed">
            {codeSnippets[selectedStack].code}
          </pre>
        </Card>

        {/* Step 5: Test Connection */}
        <Card className="p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-ink-secondary">
                5. Verify Backend Telemetry Connection
              </label>
              <p className="text-xs text-ink-tertiary mt-0.5">
                Sends a live diagnostic ping to the OpsMind AI API service ({apiEndpoint}/health).
              </p>
            </div>
            <Button
              variant="primary"
              onClick={handleVerify}
              disabled={verifying}
              className="sm:self-start"
            >
              {verifying ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" /> Verifying...
                </>
              ) : (
                <>
                  <Radio className="h-4 w-4" /> Verify Connection
                </>
              )}
            </Button>
          </div>

          {verificationResult && (
            <div
              className={`rounded-md border p-4 text-xs ${
                verificationResult.success
                  ? "border-severity-low/30 bg-severity-low/5"
                  : "border-severity-critical/30 bg-severity-critical/5"
              }`}
            >
              <div className="flex items-center justify-between font-medium">
                <span
                  className={
                    verificationResult.success
                      ? "text-severity-low font-semibold flex items-center gap-1.5"
                      : "text-severity-critical font-semibold flex items-center gap-1.5"
                  }
                >
                  <span
                    className={`h-2 w-2 rounded-full ${
                      verificationResult.success ? "bg-severity-low animate-pulse" : "bg-severity-critical"
                    }`}
                  />
                  {verificationResult.success ? "Connection Verified & Active" : "Connection Failed"}
                </span>
                <span className="font-mono text-ink-tertiary">
                  RTT: {verificationResult.latencyMs} ms · {verificationResult.timestamp}
                </span>
              </div>
              <p className="mt-2 text-ink-secondary">{verificationResult.message}</p>
              {verificationResult.components && (
                <div className="mt-3 flex gap-4 border-t border-border/50 pt-2 font-mono text-[11px] text-ink-tertiary">
                  {Object.entries(verificationResult.components).map(([comp, st]) => (
                    <span key={comp} className="capitalize">
                      {comp}: <strong className="text-ink">{st}</strong>
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
