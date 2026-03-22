"use client";

import type { Competitor } from "@/app/page";
import { OverviewMetrics } from "../components/overview-metrics";
import { ComparisonChart } from "../components/comparison-chart";
import { RadarComparison } from "../components/radar-comparison";
import { AllPatternAlerts } from "../components/all-pattern-alerts";
import { LandscapeSummary } from "../components/landscape-summary";

interface AllCompetitorsViewProps {
  competitors: Competitor[];
}

export function AllCompetitorsView({ competitors }: AllCompetitorsViewProps) {
  return (
    <div className="space-y-6">
      {/* Row 1: Overview metric cards */}
      <OverviewMetrics competitors={competitors} />

      {/* Row 2: Comparison chart */}
      <ComparisonChart competitors={competitors} />

      {/* Row 3: Radar chart */}
      <RadarComparison competitors={competitors} />

      {/* Row 4: All pattern alerts */}
      <AllPatternAlerts competitors={competitors} />

      {/* Row 5: Landscape summary */}
      <LandscapeSummary competitors={competitors} />
    </div>
  );
}
