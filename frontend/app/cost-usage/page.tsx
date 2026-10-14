"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Filter,
  Search,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { Card, Button } from "@/components/ui";

interface SpendingItem {
  provider: string;
  model: string;
  reqs: string;
  tokens: string;
  cost: number;
  share: number;
}

const INITIAL_SPENDING_TABLE: SpendingItem[] = [
  { provider: "OpenAI", model: "GPT-4o", reqs: "12,480", tokens: "8.2M", cost: 91.20, share: 71 },
  { provider: "Anthropic", model: "Claude 3.5 Sonnet", reqs: "4,120", tokens: "2.1M", cost: 27.10, share: 21 },
  { provider: "Pinecone", model: "Prod-Primary", reqs: "145K", tokens: "-", cost: 16.30, share: 12 },
  { provider: "Cohere", model: "Embed English", reqs: "3,240", tokens: "1.8M", cost: 8.40, share: 6 },
  { provider: "AWS", model: "Bedrock", reqs: "950", tokens: "0.4M", cost: 4.10, share: 3 },
  { provider: "Google", model: "Gemini 1.5 Pro", reqs: "320", tokens: "0.1M", cost: 2.20, share: 1 },
  { provider: "Other", model: "-", reqs: "1,240", tokens: "-", cost: 1.10, share: 1 },
];

const SAVINGS_BREAKDOWN = [
  { name: "Duplicate Prompts", amount: 18.40, color: "#38B27B" },
  { name: "Retry Loops", amount: 7.20, color: "#4C8DFF" },
  { name: "Uncapped Tokens", amount: 5.80, color: "#A855F7" },
];

const COST_ALERTS = [
  {
    id: "alt-1",
    title: "Projected over budget",
    detail: "+$30.00 expected by month end based on current burn rate.",
    time: "4h ago",
    severity: "warning",
    isIncident: false,
  },
  {
    id: "alt-2",
    title: "Budget 80% threshold reached",
    detail: "$120.00 / $150.00 limit consumed already.",
    time: "2h ago",
    severity: "warning",
    isIncident: false,
  },
  {
    id: "alt-3",
    title: "Retry-driven spending surge on POST /api/generate",
    detail: "High token waste generated due to 5xx response retry loops. Immediate mitigation recommended.",
    time: "1h ago",
    severity: "critical",
    isIncident: true,
  },
  {
    id: "alt-4",
    title: "Unusual token volume on Dev environment",
    detail: "Spike of 4.5M tokens generated outside of scheduled testing windows.",
    time: "12h ago",
    severity: "warning",
    isIncident: false,
  },
];

export default function CostUsagePage() {
  const [timeFilter, setTimeFilter] = useState("This Month");
  const [searchQuery, setSearchQuery] = useState("");
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [costFilter, setCostFilter] = useState<string>("");
  const [tokenFilter, setTokenFilter] = useState<string>("");
  const [hoveredPoint, setHoveredPoint] = useState<{
    date: string;
    actual: number | null;
    forecast: number | null;
    x: number;
    y: number;
  } | null>(null);

  const filteredSpending = useMemo(() => {
    return INITIAL_SPENDING_TABLE.filter((item) => {
      const q = searchQuery.toLowerCase();
      const matchesSearch =
        !q ||
        item.provider.toLowerCase().includes(q) ||
        item.model.toLowerCase().includes(q);

      let matchesCost = true;
      if (costFilter === "High") matchesCost = item.cost >= 50;
      if (costFilter === "Medium") matchesCost = item.cost >= 10 && item.cost < 50;
      if (costFilter === "Low") matchesCost = item.cost < 10;

      let matchesTokens = true;
      if (tokenFilter === "High")
        matchesTokens = item.tokens.includes("M") && parseFloat(item.tokens) >= 2.0;
      if (tokenFilter === "Medium")
        matchesTokens = item.tokens.includes("M") && parseFloat(item.tokens) < 2.0;
      if (tokenFilter === "Low")
        matchesTokens = item.tokens === "-" || item.tokens.includes("K");

      return matchesSearch && matchesCost && matchesTokens;
    });
  }, [searchQuery, costFilter, tokenFilter]);

  // Chart data points
  // Width: 800, Height: 240, Padding: 40
  const chartPoints = [
    { date: "Oct 01", actual: 18.20, forecast: null, x: 50, yActual: 200, yForecast: null },
    { date: "Oct 05", actual: 42.40, forecast: null, x: 170, yActual: 168, yForecast: null },
    { date: "Oct 10", actual: 75.10, forecast: null, x: 290, yActual: 124, yForecast: null },
    { date: "Oct 15 (Today)", actual: 128.40, forecast: 128.40, x: 410, yActual: 58, yForecast: 58 },
    { date: "Oct 20", actual: null, forecast: 145.20, x: 530, yActual: null, yForecast: 42 },
    { date: "Oct 25", actual: null, forecast: 165.70, x: 650, yActual: null, yForecast: 25 },
    { date: "Oct 31", actual: null, forecast: 180.00, x: 770, yActual: null, yForecast: 12 },
  ];

  const budgetY = 38; // $150 budget limit line

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl px-5 py-6 sm:px-8 sm:py-8 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border pb-4">
          <div>
            <h1 className="text-xl font-semibold text-ink">Cost &amp; Usage</h1>
            <p className="mt-0.5 text-xs text-ink-secondary">
              AI model token attribution, infrastructure spend, and budget forecasts
            </p>
          </div>

          <select
            value={timeFilter}
            onChange={(e) => setTimeFilter(e.target.value)}
            className="rounded-md border border-border bg-surface px-3 py-1.5 text-xs font-medium text-ink focus:border-accent focus:outline-none cursor-pointer"
          >
            <option>This Month</option>
            <option>Previous Month</option>
            <option>Past 3 Months</option>
            <option>Future Prediction</option>
          </select>
        </div>

        {/* 1. KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Card className="p-5 flex flex-col justify-between">
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-xs font-semibold text-ink-secondary uppercase tracking-wider">
                Current Spend
              </span>
              <span className="text-[10px] text-ink-tertiary bg-surface-raised px-1.5 py-0.5 rounded border border-border">
                Actual
              </span>
            </div>
            <span className="text-3xl font-mono font-bold text-ink my-1">$128.40</span>
            <div className="text-xs text-ink-tertiary">85.6% of monthly budget</div>
          </Card>

          <Card className="p-5 flex flex-col justify-between">
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-xs font-semibold text-ink-secondary uppercase tracking-wider">
                Monthly Budget
              </span>
              <span className="text-[10px] text-ink-tertiary bg-surface-raised px-1.5 py-0.5 rounded border border-border">
                Target
              </span>
            </div>
            <span className="text-3xl font-mono font-bold text-ink my-1">$150.00</span>
            <div className="text-xs text-severity-low">$21.60 remaining</div>
          </Card>

          <Card className="p-5 flex flex-col justify-between border-severity-critical/30">
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-xs font-semibold text-ink-secondary uppercase tracking-wider">
                Projected Spend
              </span>
              <span className="text-[10px] font-mono text-severity-critical bg-severity-critical/10 border border-severity-critical/30 px-1.5 py-0.5 rounded">
                Exceeds Budget
              </span>
            </div>
            <span className="text-3xl font-mono font-bold text-severity-critical my-1">$180.00</span>
            <div className="text-xs font-mono text-severity-critical flex items-center">
              +$30.00 over budget <TrendingUp className="w-3.5 h-3.5 ml-1" />
            </div>
          </Card>
        </div>

        {/* 2. Main Spending Timeline Chart */}
        <Card className="p-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <div>
              <h2 className="text-sm font-semibold text-ink">Total Spending Timeline</h2>
              <span className="text-xs text-ink-tertiary">Historical Spend &amp; Predictive Runway</span>
            </div>

            <div className="flex items-center gap-3.5 text-xs font-mono bg-surface-raised px-3 py-1.5 rounded border border-border">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 bg-accent rounded-sm" />
                <span className="text-ink-secondary">Actual Spend</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-0 border-b-2 border-dashed border-severity-high" />
                <span className="text-ink-secondary">Forecast</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-0 border-b-2 border-dashed border-severity-critical" />
                <span className="text-ink-secondary">Budget Limit ($150)</span>
              </div>
            </div>
          </div>

          {/* SVG Chart */}
          <div className="relative w-full h-[240px]">
            <svg
              viewBox="0 0 820 240"
              className="w-full h-full overflow-visible"
              preserveAspectRatio="none"
            >
              {/* Grid Lines */}
              <line x1="40" y1="20" x2="800" y2="20" stroke="#232A35" strokeDasharray="3 3" />
              <line x1="40" y1="80" x2="800" y2="80" stroke="#232A35" strokeDasharray="3 3" />
              <line x1="40" y1="140" x2="800" y2="140" stroke="#232A35" strokeDasharray="3 3" />
              <line x1="40" y1="200" x2="800" y2="200" stroke="#232A35" strokeDasharray="3 3" />

              {/* Y Axis Labels */}
              <text x="30" y="24" fill="#5B6472" fontSize="10" textAnchor="end">$180</text>
              <text x="30" y="84" fill="#5B6472" fontSize="10" textAnchor="end">$120</text>
              <text x="30" y="144" fill="#5B6472" fontSize="10" textAnchor="end">$60</text>
              <text x="30" y="204" fill="#5B6472" fontSize="10" textAnchor="end">$0</text>

              {/* Budget Limit Reference Line */}
              <line
                x1="40"
                y1={budgetY}
                x2="800"
                y2={budgetY}
                stroke="#E5484D"
                strokeWidth="1.5"
                strokeDasharray="4 4"
              />
              <text x="795" y={budgetY - 5} fill="#E5484D" fontSize="9" fontWeight="bold" textAnchor="end">
                BUDGET LIMIT ($150.00)
              </text>

              {/* Actual Spend Area Gradient */}
              <defs>
                <linearGradient id="spendAreaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#4C8DFF" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#4C8DFF" stopOpacity="0.0" />
                </linearGradient>
              </defs>
              <polygon
                points="50,200 50,200 170,168 290,124 410,58 410,200"
                fill="url(#spendAreaGrad)"
              />

              {/* Actual Spend Line */}
              <polyline
                fill="none"
                stroke="#4C8DFF"
                strokeWidth="2.5"
                points="50,200 170,168 290,124 410,58"
              />

              {/* Forecast Line */}
              <polyline
                fill="none"
                stroke="#F5A623"
                strokeWidth="2.5"
                strokeDasharray="5 5"
                points="410,58 530,42 650,25 770,12"
              />

              {/* Dots & Hit areas */}
              {chartPoints.map((pt, idx) => {
                const y = pt.yActual ?? pt.yForecast!;
                const isForecast = pt.actual === null;
                return (
                  <g key={idx}>
                    <circle
                      cx={pt.x}
                      cy={y}
                      r="4"
                      fill={isForecast ? "#F5A623" : "#4C8DFF"}
                      stroke="#12161B"
                      strokeWidth="2"
                    />
                    {/* Invisible hover area */}
                    <circle
                      cx={pt.x}
                      cy={y}
                      r="16"
                      fill="transparent"
                      className="cursor-pointer"
                      onMouseEnter={() =>
                        setHoveredPoint({
                          date: pt.date,
                          actual: pt.actual,
                          forecast: pt.forecast,
                          x: pt.x,
                          y,
                        })
                      }
                      onMouseLeave={() => setHoveredPoint(null)}
                    />
                    {/* X Axis Label */}
                    <text
                      x={pt.x}
                      y="225"
                      fill="#93A0B4"
                      fontSize="10"
                      textAnchor="middle"
                    >
                      {pt.date}
                    </text>
                  </g>
                );
              })}
            </svg>

            {/* Hover Tooltip */}
            {hoveredPoint && (
              <div
                className="absolute pointer-events-none rounded border border-border bg-surface p-2.5 text-xs shadow-xl min-w-[140px] font-mono z-10"
                style={{
                  left: `${(hoveredPoint.x / 820) * 100}%`,
                  top: `${Math.max(10, hoveredPoint.y - 65)}px`,
                  transform: "translateX(-50%)",
                }}
              >
                <div className="text-ink-tertiary mb-1 pb-1 border-b border-border">
                  {hoveredPoint.date}
                </div>
                {hoveredPoint.actual !== null && (
                  <div className="flex justify-between py-0.5 text-accent">
                    <span>Actual:</span>
                    <span>${hoveredPoint.actual.toFixed(2)}</span>
                  </div>
                )}
                {hoveredPoint.forecast !== null && (
                  <div className="flex justify-between py-0.5 text-severity-high">
                    <span>Forecast:</span>
                    <span>${hoveredPoint.forecast.toFixed(2)}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>

        {/* 3. Detailed Breakdown Table */}
        <Card className="overflow-hidden">
          <div className="p-4 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-ink">Model &amp; Provider Breakdown</h2>
              <span className="text-xs text-ink-tertiary">Real-time resource allocation</span>
            </div>

            <div className="flex gap-2">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-tertiary" />
                <input
                  type="text"
                  placeholder="Search providers or models..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-48 bg-base border border-border rounded-md px-2.5 py-1.5 pl-8 text-xs text-ink focus:border-accent focus:outline-none"
                />
              </div>

              {/* Filter Popover */}
              <div className="relative">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setIsFilterOpen(!isFilterOpen)}
                  className={costFilter || tokenFilter ? "border-accent text-accent" : ""}
                >
                  <Filter className="h-3.5 w-3.5 mr-1" />
                  Filter
                  {(costFilter || tokenFilter) && (
                    <span className="w-1.5 h-1.5 bg-accent rounded-full ml-1" />
                  )}
                </Button>

                {isFilterOpen && (
                  <div className="absolute right-0 mt-2 w-48 bg-surface-raised border border-border rounded-md shadow-2xl z-20 p-3 text-xs space-y-3">
                    <div>
                      <div className="text-[10px] font-semibold text-ink-tertiary uppercase tracking-wider mb-1.5">
                        Cost Tier
                      </div>
                      <div className="space-y-1">
                        {["High", "Medium", "Low"].map((lvl) => (
                          <label key={lvl} className="flex items-center gap-2 cursor-pointer text-ink">
                            <input
                              type="radio"
                              name="costFilter"
                              checked={costFilter === lvl}
                              onChange={() => setCostFilter(lvl)}
                            />
                            <span>{lvl}</span>
                          </label>
                        ))}
                      </div>
                    </div>

                    <div>
                      <div className="text-[10px] font-semibold text-ink-tertiary uppercase tracking-wider mb-1.5">
                        Token Volume
                      </div>
                      <div className="space-y-1">
                        {["High", "Medium", "Low"].map((lvl) => (
                          <label key={lvl} className="flex items-center gap-2 cursor-pointer text-ink">
                            <input
                              type="radio"
                              name="tokenFilter"
                              checked={tokenFilter === lvl}
                              onChange={() => setTokenFilter(lvl)}
                            />
                            <span>{lvl}</span>
                          </label>
                        ))}
                      </div>
                    </div>

                    <div className="pt-2 border-t border-border flex justify-between">
                      <button
                        type="button"
                        onClick={() => {
                          setCostFilter("");
                          setTokenFilter("");
                        }}
                        className="text-[11px] text-severity-critical hover:underline"
                      >
                        Reset
                      </button>
                      <button
                        type="button"
                        onClick={() => setIsFilterOpen(false)}
                        className="text-[11px] text-ink hover:underline"
                      >
                        Done
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="overflow-x-auto max-h-[280px]">
            <table className="w-full text-left text-xs whitespace-nowrap">
              <thead className="sticky top-0 bg-surface-raised border-b border-border text-ink-tertiary uppercase text-[10px] tracking-wider">
                <tr>
                  <th className="py-3 px-4">Provider</th>
                  <th className="py-3 px-4">Model</th>
                  <th className="py-3 px-4 text-right">Requests</th>
                  <th className="py-3 px-4 text-right">Tokens</th>
                  <th className="py-3 px-4 text-right">Cost</th>
                  <th className="py-3 px-4 text-right">Share</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredSpending.length > 0 ? (
                  filteredSpending.map((row, idx) => (
                    <tr key={idx} className="hover:bg-surface-hover/50">
                      <td className="py-3 px-4 text-ink font-medium">{row.provider}</td>
                      <td className="py-3 px-4 text-ink-secondary font-mono">{row.model}</td>
                      <td className="py-3 px-4 text-right font-mono text-ink-secondary">{row.reqs}</td>
                      <td className="py-3 px-4 text-right font-mono text-ink-secondary">{row.tokens}</td>
                      <td className="py-3 px-4 text-right font-mono text-ink font-semibold">
                        ${row.cost.toFixed(2)}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-16 bg-surface-raised h-1.5 rounded-full overflow-hidden border border-border">
                            <div className="bg-accent h-full" style={{ width: `${row.share}%` }} />
                          </div>
                          <span className="font-mono text-ink-tertiary text-[10px] w-6">
                            {row.share}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-ink-tertiary">
                      No records match the current filter criteria.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {/* 4. Bottom Grid: Potential Savings & Alerts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Potential Savings */}
          <Card className="p-5 flex flex-col justify-between">
            <div className="flex items-center justify-between border-b border-border pb-3 mb-4">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-severity-low" />
                <h2 className="text-sm font-semibold text-ink">Potential Savings</h2>
              </div>
              <span className="text-xs font-mono font-medium text-severity-low bg-severity-low/10 px-2 py-0.5 rounded border border-severity-low/30">
                $31.40 Total est.
              </span>
            </div>

            <div className="space-y-3.5 my-2">
              {SAVINGS_BREAKDOWN.map((item) => (
                <div key={item.name} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-ink-secondary">{item.name}</span>
                    <span className="font-mono font-medium text-ink">${item.amount.toFixed(2)}</span>
                  </div>
                  <div className="w-full bg-surface-raised h-2 rounded-full overflow-hidden border border-border">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${(item.amount / 31.4) * 100}%`,
                        backgroundColor: item.color,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="pt-3 border-t border-border mt-3 text-right">
              <Link
                href="/reports"
                className="inline-flex items-center gap-1.5 text-xs text-accent hover:underline"
              >
                View full savings report <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </Card>

          {/* Cost Alerts & Active Incidents */}
          <Card className="p-5 flex flex-col justify-between">
            <div className="flex items-center justify-between border-b border-border pb-3 mb-4">
              <h2 className="text-sm font-semibold text-ink">Cost Alerts &amp; Incidents</h2>
              <span className="text-xs text-ink-tertiary">Requires attention</span>
            </div>

            <div className="space-y-3 overflow-y-auto max-h-[220px]">
              {COST_ALERTS.map((alert) => (
                <div
                  key={alert.id}
                  className={`p-3 rounded-md border text-xs bg-base ${
                    alert.severity === "critical"
                      ? "border-severity-critical/40"
                      : "border-border hover:border-border-strong"
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    <AlertTriangle
                      className={`h-4 w-4 flex-shrink-0 mt-0.5 ${
                        alert.severity === "critical" ? "text-severity-critical" : "text-severity-high"
                      }`}
                    />
                    <div className="flex-1">
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="font-semibold text-ink">{alert.title}</span>
                        {alert.isIncident && (
                          <span className="text-[9px] font-bold uppercase tracking-wider text-severity-critical border border-severity-critical/30 px-1.5 py-0.5 rounded bg-severity-critical/10">
                            Active Incident
                          </span>
                        )}
                      </div>
                      <p className="text-ink-secondary text-[11px] leading-relaxed mb-2">
                        {alert.detail}
                      </p>
                      {alert.isIncident ? (
                        <Link
                          href="/incidents"
                          className="inline-flex items-center gap-1.5 border border-severity-critical/60 text-severity-critical hover:bg-severity-critical/10 text-[11px] font-medium px-2.5 py-1 rounded transition-colors"
                        >
                          Go to Incident Page <ArrowRight className="h-3 w-3" />
                        </Link>
                      ) : (
                        <span className="text-[10px] text-ink-tertiary">{alert.time}</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
