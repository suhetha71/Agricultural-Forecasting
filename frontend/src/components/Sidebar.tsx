import React from "react";
import {
  TrendingUp,
  BarChart3,
  GitCompare,
  BrainCircuit,
  ShieldCheck,
  Database,
  LayoutDashboard,
  Sprout,
  Activity,
} from "lucide-react";

interface SidebarProps {
  activeTab: string;
  onSelectTab: (tab: string) => void;
  systemStatus: string;
}

const navItems = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "price_analysis", label: "Price Analysis", icon: BarChart3 },
  { id: "forecasting", label: "Forecasting", icon: TrendingUp },
  { id: "market_comparison", label: "Market Comparison", icon: GitCompare },
  { id: "decision_support", label: "Decision Support", icon: BrainCircuit },
  { id: "model_validation", label: "Model Validation", icon: ShieldCheck },
  { id: "data_sources", label: "Data Sources", icon: Database },
];

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, onSelectTab, systemStatus }) => {
  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <div style={{ padding: "24px 20px", borderBottom: "1px solid var(--border-subtle)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "8px" }}>
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "10px",
              background: "linear-gradient(135deg, #10b981 0%, #047857 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              boxShadow: "0 4px 12px rgba(16, 185, 129, 0.3)",
            }}
          >
            <Sprout size={24} />
          </div>
          <div>
            <h1
              style={{
                fontSize: "0.95rem",
                fontWeight: 700,
                color: "#fff",
                letterSpacing: "-0.01em",
                lineHeight: 1.25,
              }}
            >
              Agricultural Market Price Forecasting &amp; Decision Support System
            </h1>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "12px" }}>
          <span
            style={{
              display: "inline-block",
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              backgroundColor: systemStatus === "healthy" ? "#10b981" : "#f59e0b",
              boxShadow: systemStatus === "healthy" ? "0 0 8px #10b981" : "none",
            }}
          />
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 500 }}>
            {systemStatus === "healthy" ? "Backend Online & Connected" : "Connecting to Engine..."}
          </span>
        </div>
      </div>

      {/* Navigation Items */}
      <nav style={{ padding: "16px 12px", flex: 1, display: "flex", flexDirection: "column", gap: "4px" }}>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                padding: "12px 14px",
                width: "100%",
                borderRadius: "var(--radius-sm)",
                backgroundColor: isActive ? "rgba(16, 185, 129, 0.12)" : "transparent",
                color: isActive ? "var(--emerald-400)" : "var(--text-muted)",
                border: isActive ? "1px solid rgba(16, 185, 129, 0.25)" : "1px solid transparent",
                cursor: "pointer",
                fontWeight: isActive ? 600 : 500,
                fontSize: "0.875rem",
                textAlign: "left",
                transition: "all 0.15s ease",
              }}
            >
              <Icon size={18} style={{ color: isActive ? "var(--emerald-400)" : "var(--text-dim)" }} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* College Project Meta Footer */}
      <div
        style={{
          padding: "16px 20px",
          borderTop: "1px solid var(--border-subtle)",
          backgroundColor: "rgba(0, 0, 0, 0.2)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
          <Activity size={14} style={{ color: "var(--emerald-500)" }} />
          <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-main)" }}>
            Agri-Forecast Engine v1.0
          </span>
        </div>
        <p style={{ fontSize: "0.7rem", color: "var(--text-dim)" }}>
          Official AGMARKNET / OGD India Standards
        </p>
      </div>
    </aside>
  );
};
