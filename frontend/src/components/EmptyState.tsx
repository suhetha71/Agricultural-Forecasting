import React from "react";
import { LucideIcon, Database } from "lucide-react";

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: LucideIcon;
  actionText?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon: Icon = Database,
  actionText,
  onAction,
}) => {
  return (
    <div className="glass-card" style={{ padding: "56px 24px", textAlign: "center" }}>
      <div
        style={{
          width: "60px",
          height: "60px",
          borderRadius: "16px",
          background: "rgba(255, 255, 255, 0.04)",
          border: "1px solid var(--border-subtle)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          margin: "0 auto 16px",
          color: "var(--emerald-400)",
        }}
      >
        <Icon size={30} />
      </div>
      <h3 style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--text-main)", marginBottom: "8px" }}>
        {title}
      </h3>
      <p style={{ color: "var(--text-muted)", fontSize: "0.875rem", maxWidth: "460px", margin: "0 auto 20px" }}>
        {description}
      </p>
      {actionText && onAction && (
        <button className="btn btn-primary" onClick={onAction}>
          {actionText}
        </button>
      )}
    </div>
  );
};
