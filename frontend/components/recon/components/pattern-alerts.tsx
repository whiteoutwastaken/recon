"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import type { Competitor } from "@/app/page";
import { Zap, TrendingUp, AlertTriangle, Users, MessageSquare, ArrowRight } from "lucide-react";
import { fetchPatterns, queryAgent } from "@/lib/api";

const patternTypeConfig: Record<string, any> = {
  hiring_surge: { icon: Users, label: "Hiring Surge → Launch Signal", color: "text-foreground", bg: "bg-foreground/10" },
  sentiment_shift: { icon: TrendingUp, label: "Sentiment Shift Pattern", color: "text-foreground/70", bg: "bg-foreground/5" },
  competitive_move: { icon: AlertTriangle, label: "Competitive Response", color: "text-warning", bg: "bg-warning/10" },
  market_signal: { icon: Zap, label: "Market Signal", color: "text-foreground/80", bg: "bg-foreground/10" },
};

const defaultConfig = { icon: Zap, label: "Pattern", color: "text-foreground/80", bg: "bg-foreground/10" };

export function PatternAlerts({ competitor }: { competitor: Competitor }) {
  const [patterns, setPatterns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [asking, setAsking] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  useEffect(() => {
    setLoading(true);
    fetchPatterns(competitor.id)
      .then(setPatterns)
      .catch(() => setPatterns([]))
      .finally(() => setLoading(false));
  }, [competitor.id]);

  const handleAsk = async (pattern: any) => {
    setAsking(pattern.pattern_id);
    try {
      const result = await queryAgent(`Tell me more about this pattern: ${pattern.description}`);
      setAnswers((prev) => ({ ...prev, [pattern.pattern_id]: result.answer || "No response." }));
    } catch {
      setAnswers((prev) => ({ ...prev, [pattern.pattern_id]: "Agent not available." }));
    }
    setAsking(null);
  };

  if (loading) return <div className="h-32 bg-secondary/30 rounded-xl animate-pulse" />;
  if (!patterns.length) return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 delay-200">
      <h3 className="text-base font-semibold text-foreground mb-2">Pattern Alerts</h3>
      <p className="text-sm text-muted-foreground">No patterns detected for {competitor.name} yet.</p>
    </div>
  );

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 delay-200">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-foreground">Pattern Alerts</h3>
          <p className="text-sm text-muted-foreground mt-0.5">AI-detected patterns involving {competitor.name}</p>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {patterns.map((pattern, index) => {
          const config = patternTypeConfig[pattern.type] || defaultConfig;
          const Icon = config.icon;
          const conf = Math.round((pattern.confidence || 0) * 100);
          return (
            <div key={pattern.pattern_id} className="bg-card border border-border rounded-xl p-5 hover:border-foreground/30 transition-all duration-300 animate-in fade-in slide-in-from-bottom-2" style={{ animationDelay: `${index * 100}ms`, animationFillMode: "both" }}>
              <div className={cn("inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium mb-3", config.bg, config.color)}>
                <Icon className="w-3 h-3" />
                {config.label}
              </div>
              <h4 className="text-sm font-semibold text-foreground mb-2">{pattern.description}</h4>
              <div className="mb-4">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-muted-foreground">Confidence</span>
                  <span className={cn("font-medium", conf >= 80 ? "text-foreground" : conf >= 50 ? "text-muted-foreground" : "text-destructive")}>{conf}%</span>
                </div>
                <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                  <div className={cn("h-full rounded-full transition-all duration-500", conf >= 80 ? "bg-foreground" : conf >= 50 ? "bg-foreground/50" : "bg-destructive")} style={{ width: `${conf}%` }} />
                </div>
              </div>
              {pattern.prediction && (
                <div className="p-3 rounded-lg bg-secondary/50 border border-border mb-4">
                  <div className="flex items-center gap-1.5 text-xs font-medium text-foreground/80 mb-1"><ArrowRight className="w-3 h-3" />Prediction</div>
                  <p className="text-xs text-muted-foreground">{pattern.prediction}</p>
                </div>
              )}
              {answers[pattern.pattern_id] && (
                <div className="p-3 rounded-lg bg-secondary/30 border border-border mb-4">
                  <p className="text-xs text-muted-foreground leading-relaxed">{answers[pattern.pattern_id]}</p>
                </div>
              )}
              <button
                onClick={() => handleAsk(pattern)}
                disabled={asking === pattern.pattern_id}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium bg-secondary text-foreground hover:bg-secondary/80 transition-all duration-200 disabled:opacity-50"
              >
                <MessageSquare className="w-3.5 h-3.5" />
                {asking === pattern.pattern_id ? "Asking..." : "Ask Recon about this"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}