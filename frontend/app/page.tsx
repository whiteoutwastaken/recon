"use client";

import { useState, useEffect } from "react";
import { Sidebar } from "@/components/recon/sidebar";
import { TopBar } from "@/components/recon/top-bar";
import { CompetitorView } from "@/components/recon/views/competitor-view";
import { AllCompetitorsView } from "@/components/recon/views/all-competitors-view";
import { VoiceAgentPanel } from "@/components/recon/voice-agent-panel";
import { fetchCompetitors, runIngest, detectPatterns } from "@/lib/api";

export type Competitor = {
  id: string;
  name: string;
  description: string;
  sentiment: "positive" | "neutral" | "negative";
};

export type AgentStatus = {
  discovery: { status: "running" | "complete"; message: string };
  news: { status: "running" | "complete"; message: string };
  jobs: { status: "running" | "complete"; message: string };
  patterns: { status: "running" | "complete"; message: string };
  lastUpdated: string;
};

export default function ReconDashboard() {
  const [selectedCompetitor, setSelectedCompetitor] = useState<string | null>(null);
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [agentStatus, setAgentStatus] = useState<AgentStatus>({
    discovery: { status: "complete", message: "Ready" },
    news: { status: "complete", message: "Ready" },
    jobs: { status: "complete", message: "Ready" },
    patterns: { status: "complete", message: "Ready" },
    lastUpdated: "Just now",
  });
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [searchProgress, setSearchProgress] = useState("");
  const [voicePanelOpen, setVoicePanelOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCompetitors()
      .then((data: any[]) => {
        const mapped: Competitor[] = data.map((c) => ({
          id: c.id,
          name: c.name,
          description: c.industry || c.description || "",
          sentiment: "neutral" as const,
        }));
        setCompetitors(mapped);
        setAgentStatus((prev) => ({
          ...prev,
          discovery: { status: "complete", message: `Found ${mapped.length} competitors` },
        }));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSearch = async (query: string) => {
    if (!query.trim()) return;
    setIsSearching(true);
    setSearchQuery(query);
    const steps = ["Scanning competitors...", "Scraping news...", "Analyzing hiring signals...", "Detecting patterns...", "Done."];
    for (const step of steps) {
      setSearchProgress(step);
      await new Promise((r) => setTimeout(r, 700));
    }
    setIsSearching(false);
    setSearchProgress("");
  };

  const handleRefresh = async () => {
    if (!selectedCompetitor) return;
    setIsSearching(true);
    setSearchProgress("Refreshing intel...");
    setAgentStatus((prev) => ({
      ...prev,
      news: { status: "running", message: "Scraping news..." },
      jobs: { status: "running", message: "Analyzing jobs..." },
    }));
    try {
      await runIngest(selectedCompetitor);
      setAgentStatus((prev) => ({
        ...prev,
        news: { status: "complete", message: "Articles updated" },
        jobs: { status: "complete", message: "Signals updated" },
        lastUpdated: "Just now",
      }));
    } catch {}
    setIsSearching(false);
    setSearchProgress("");
  };

  const handleDetectPatterns = async () => {
    setAgentStatus((prev) => ({ ...prev, patterns: { status: "running", message: "Detecting..." } }));
    try {
      const result = await detectPatterns();
      setAgentStatus((prev) => ({
        ...prev,
        patterns: { status: "complete", message: `${result.count || 0} patterns detected` },
        lastUpdated: "Just now",
      }));
    } catch {
      setAgentStatus((prev) => ({ ...prev, patterns: { status: "complete", message: "Agent not ready" } }));
    }
  };

  const currentCompetitor = competitors.find((c) => c.id === selectedCompetitor);

  return (
    <div className="flex flex-col min-h-screen bg-background">
      <TopBar
        searchQuery={searchQuery}
        onSearch={handleSearch}
        isSearching={isSearching}
        searchProgress={searchProgress}
        onRefresh={handleRefresh}
        onVoiceClick={() => setVoicePanelOpen(true)}
      />
      <div className="flex flex-1 pt-16">
        <Sidebar
          competitors={competitors}
          selectedCompetitor={selectedCompetitor}
          onSelectCompetitor={setSelectedCompetitor}
          onRefresh={handleRefresh}
          onDetectPatterns={handleDetectPatterns}
          collapsed={sidebarCollapsed}
          onCollapsedChange={setSidebarCollapsed}
          agentStatus={agentStatus}
        />
        <main className={`flex-1 p-6 overflow-auto transition-all duration-300 ease-out ${sidebarCollapsed ? "ml-[72px]" : "ml-[260px]"} ${voicePanelOpen ? "mr-[340px]" : ""}`}>
          {loading ? (
            <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">Connecting to backend...</div>
          ) : (
            <div key={selectedCompetitor ?? "all"} className="animate-in fade-in slide-in-from-bottom-4 duration-500">
              {selectedCompetitor && currentCompetitor ? (
                <CompetitorView competitor={currentCompetitor} />
              ) : (
                <AllCompetitorsView competitors={competitors} />
              )}
            </div>
          )}
        </main>
        <VoiceAgentPanel isOpen={voicePanelOpen} onClose={() => setVoicePanelOpen(false)} />
      </div>
    </div>
  );
}