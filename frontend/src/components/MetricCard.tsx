import React from "react";
import { LucideIcon, TrendingUp, TrendingDown, Minus } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  changePct?: number | null;
  icon: LucideIcon;
  badgeText?: string;
  badgeVariant?: "emerald" | "amber" | "rose" | "indigo";
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subtext,
  changePct,
  icon: Icon,
  badgeText,
  badgeVariant = "emerald",
}) => {
  return (
    <div className="glass-card stat-card">
      <div style={{ zIndex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
          <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-muted)" }}>
            {label}
          </span>
          {badgeText && (
            <span className={`badge badge-${badgeVariant}`} style={{ fontSize: "0.65rem", padding: "2px 6px" }}>
              {badgeText}
            </span>
          )}
        </div>

        <div style={{ fontSize: "1.65rem", fontWeight: 800, color: "#fff", letterSpacing: "-0.02em", marginBottom: "6px" }}>
          {value}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          {changePct !== undefined && changePct !== null && (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "2px",
                fontSize: "0.75rem",
                fontWeight: 700,
                color: changePct > 0 ? "var(--emerald-400)" : changePct < 0 ? "var(--rose-500)" : "var(--text-muted)",
              }}
            >
              {changePct > 0 ? (
                <TrendingUp size={14} />
              ) : changePct < 0 ? (
                <TrendingDown size={14} />
              ) : (
                <Minus size={14} />
              )}
              {changePct > 0 ? `+${changePct}%` : `${changePct}%`}
            </span>
          )}
          {subtext && (
            <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
              {subtext}
            </span>
          )}
        </div>
      </div>

      <div
        style={{
          width: "44px",
          height: "44px",
          borderRadius: "12px",
          background: "rgba(255, 255, 255, 0.04)",
          border: "1px solid var(--border-subtle)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--emerald-400)",
          zIndex: 1,
        }}
      >
        <Icon size={22} />
      </div>
    </div>
  );
};
