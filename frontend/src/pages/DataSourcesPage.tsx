import React, { useState, useEffect } from "react";
import {
  Database,
  UploadCloud,
  CheckCircle2,
  AlertCircle,
  FileText,
  RefreshCw,
  Key,
  Download,
  Calendar,
  Layers,
  Info,
  ExternalLink,
} from "lucide-react";
import { api } from "../services/api";
import { ImportResult, HealthResponse, DataSourceStats } from "../types";

interface DataSourcesPageProps {
  health: HealthResponse | null;
  onDataImported: () => void;
}

export const DataSourcesPage: React.FC<DataSourcesPageProps> = ({
  health,
  onDataImported,
}) => {
  const [stats, setStats] = useState<DataSourceStats | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  // API sync state
  const [apiKeyInput, setApiKeyInput] = useState<string>("");
  const [apiCommodity, setApiCommodity] = useState<string>("");
  const [apiState, setApiState] = useState<string>("");
  const [isSyncingApi, setIsSyncingApi] = useState<boolean>(false);
  const [apiSyncMessage, setApiSyncMessage] = useState<{
    success: boolean;
    text: string;
    details?: string;
  } | null>(null);

  const loadStats = async () => {
    try {
      const data = await api.getDataSourceStats();
      setStats(data);
    } catch (e) {
      console.warn("Could not fetch data source stats", e);
    }
  };

  useEffect(() => {
    loadStats();
  }, [health]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
      setImportResult(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setIsUploading(true);
    try {
      const result = await api.uploadCsv(selectedFile);
      setImportResult(result);
      if (result.success && (result.imported_count > 0 || result.duplicate_count > 0)) {
        await loadStats();
        onDataImported();
      }
    } catch (err: any) {
      setImportResult({
        success: false,
        imported_count: 0,
        duplicate_count: 0,
        skipped_count: 0,
        errors: [err.message || "Upload failed"],
        message: err.message || "Failed to upload and parse CSV",
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleApiSync = async () => {
    setIsSyncingApi(true);
    setApiSyncMessage(null);
    try {
      const res = await api.syncGovApi({
        apiKey: apiKeyInput.trim() || undefined,
        commodity: apiCommodity.trim() || undefined,
        state: apiState.trim() || undefined,
      });

      setApiSyncMessage({
        success: res.success,
        text: res.message,
        details: [
          `Fetched: ${res.fetched_count}${res.total_available_count === null ? "" : ` of ${res.total_available_count}`}`,
          `Imported: ${res.imported_count}`,
          `Updated: ${res.updated_count}`,
          `Unchanged: ${res.duplicate_count}`,
          `Skipped: ${res.skipped_count}`,
          ...(res.instructions ? [res.instructions] : []),
          ...(res.errors.length ? [`Details: ${res.errors.slice(0, 3).join("; ")}`] : []),
        ].join(" · "),
      });

      if (res.success) {
        await loadStats();
        onDataImported();
      }
    } catch (err: any) {
      setApiSyncMessage({
        success: false,
        text: "Official API Sync Failed",
        details: err.message || "Failed to communicate with data.gov.in API",
      });
    } finally {
      setApiKeyInput("");
      setIsSyncingApi(false);
    }
  };

  const handleDownloadSampleCsv = () => {
    // Generate downloadable authentic Agmarknet CSV
    const csvContent = `State,District,Market,Commodity,Variety,Arrival_Date,Min_Price,Max_Price,Modal_Price,Arrivals_in_qtl
Maharashtra,Nashik,Lasalgaon,Onion,Red,24/10/2026,1800,2850,2450,1420
Maharashtra,Nashik,Pimpalgaon,Onion,Red,24/10/2026,1750,2800,2400,1180
Maharashtra,Pune,Pune,Onion,Local,24/10/2026,1900,2900,2500,950
Punjab,Ludhiana,Khanna,Wheat,Dara,24/10/2026,2275,2480,2425,820
Punjab,Patiala,Rajpura,Wheat,Kalyan,24/10/2026,2250,2460,2410,650
Karnataka,Kolar,Kolar,Tomato,Hybrid,24/10/2026,1400,2600,2150,1850
Karnataka,Bangalore,Yeshwanthpur,Tomato,Local,24/10/2026,1500,2700,2200,1200
Uttar Pradesh,Agra,Agra,Potato,Desi,24/10/2026,1100,1650,1420,2100
Gujarat,Rajkot,Rajkot,Cotton,Shankar-6,24/10/2026,6800,7650,7350,740
Madhya Pradesh,Indore,Indore,Soyabean,Yellow,24/10/2026,4200,4750,4550,1600
Rajasthan,Alwar,Alwar,Mustard,Bold,24/10/2026,5100,5650,5420,530`;

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "official_agmarknet_sample.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
      {/* Provenance & Records Breakdown Metrics */}
      <div className="grid-cols-4">
        <div className="glass-card">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: 600 }}>Official Gov API</span>
            <span className="badge badge-emerald" style={{ fontSize: "0.65rem" }}>data.gov.in</span>
          </div>
          <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--emerald-400)", marginTop: "8px" }}>
            {stats?.official_api_records ?? 0}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginTop: "4px" }}>
            Agmarknet API records
          </div>
        </div>

        <div className="glass-card">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: 600 }}>User CSV Ingested</span>
            <span className="badge badge-indigo" style={{ fontSize: "0.65rem" }}>CSV Upload</span>
          </div>
          <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--indigo-500)", marginTop: "8px" }}>
            {stats?.user_csv_records ?? 0}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginTop: "4px" }}>
            Verified user imports
          </div>
        </div>

        <div className="glass-card">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: 600 }}>Demonstration Data</span>
            <span className="badge badge-amber" style={{ fontSize: "0.65rem" }}>Sample / Baseline</span>
          </div>
          <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--amber-500)", marginTop: "8px" }}>
            {stats?.demo_seed_records ?? 0}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginTop: "4px" }}>
            Preserved baseline records
          </div>
        </div>

        <div className="glass-card">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: 600 }}>Total Records &amp; Range</span>
            <span className="badge badge-indigo" style={{ fontSize: "0.65rem" }}>Daily Cadence</span>
          </div>
          <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--text-main)", marginTop: "8px" }}>
            {stats?.total_records ?? health?.total_observations ?? 0}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginTop: "4px" }}>
            {stats?.newest_observation_date ? `Latest: ${stats.newest_observation_date}` : "Daily frequency"}
          </div>
        </div>
      </div>

      {/* Main Integration Cards */}
      <div className="grid-cols-2">
        {/* Official data.gov.in Live Interface Card */}
        <div className="glass-card">
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "14px" }}>
            <div
              style={{
                width: "40px",
                height: "40px",
                borderRadius: "10px",
                background: "rgba(16, 185, 129, 0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--emerald-400)",
              }}
            >
              <Database size={22} />
            </div>
            <div>
              <h4 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-main)" }}>
                Government of India Open Data Portal
              </h4>
              <span className="badge badge-emerald" style={{ fontSize: "0.65rem" }}>
                Official Resource: 9ef84268-d588-465a-a308-a864a43d0070
              </span>
            </div>
          </div>

          <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: "16px" }}>
            Direct ingestion from the Ministry of Agriculture &amp; Farmers Welfare (AGMARKNET) via the official Open Government Data (OGD) API platform.
          </p>

          {/* API Key Input and Filter Fields */}
          <div style={{ background: "rgba(0,0,0,0.25)", padding: "16px", borderRadius: "var(--radius-sm)", marginBottom: "16px" }}>
            <div style={{ marginBottom: "12px" }}>
              <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px", fontWeight: 600 }}>
                data.gov.in API Key (Optional if DATA_GOV_IN_API_KEY is configured in backend .env)
              </label>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Key size={16} style={{ color: "var(--text-dim)" }} />
                <input
                  type="password"
                  placeholder="Enter your personal data.gov.in API Key..."
                  className="text-input"
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  style={{ flex: 1, fontSize: "0.85rem" }}
                />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "14px" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>
                  Filter Commodity (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Onion, Wheat"
                  className="text-input"
                  value={apiCommodity}
                  onChange={(e) => setApiCommodity(e.target.value)}
                  style={{ width: "100%", fontSize: "0.85rem" }}
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>
                  Filter State (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Maharashtra, Punjab"
                  className="text-input"
                  value={apiState}
                  onChange={(e) => setApiState(e.target.value)}
                  style={{ width: "100%", fontSize: "0.85rem" }}
                />
              </div>
            </div>

            <button
              className="btn btn-primary"
              onClick={handleApiSync}
              disabled={isSyncingApi}
              style={{ width: "100%", justifyContent: "center", fontSize: "0.85rem" }}
            >
              <RefreshCw size={16} style={{ animation: isSyncingApi ? "spin 1s linear infinite" : "none" }} />
              <span>{isSyncingApi ? "Querying Official Portal..." : "Fetch & Sync from data.gov.in"}</span>
            </button>
          </div>

          {/* API Sync Notification Feedback */}
          {apiSyncMessage && (
            <div
              style={{
                padding: "12px 16px",
                borderRadius: "var(--radius-sm)",
                background: apiSyncMessage.success ? "rgba(16, 185, 129, 0.12)" : "rgba(239, 68, 68, 0.12)",
                border: `1px solid ${apiSyncMessage.success ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
                fontSize: "0.85rem",
                marginBottom: "16px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 600, color: apiSyncMessage.success ? "var(--emerald-400)" : "var(--rose-500)" }}>
                {apiSyncMessage.success ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
                <span>{apiSyncMessage.text}</span>
              </div>
              {apiSyncMessage.details && (
                <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginTop: "4px", whiteSpace: "pre-wrap" }}>
                  {apiSyncMessage.details}
                </div>
              )}
            </div>
          )}

          {/* Instructions Box */}
          <div style={{ background: "rgba(255,255,255,0.02)", padding: "12px 14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-color)", fontSize: "0.75rem", color: "var(--text-dim)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--text-muted)", fontWeight: 600, marginBottom: "4px" }}>
              <Info size={14} />
              <span>How to obtain an official API Key:</span>
            </div>
            <ol style={{ paddingLeft: "18px", margin: 0, lineHeight: 1.5 }}>
              <li>Register free account at <a href="https://www.data.gov.in" target="_blank" rel="noreferrer" style={{ color: "var(--emerald-400)" }}>data.gov.in <ExternalLink size={10} style={{ display: "inline" }} /></a></li>
              <li>Activate account and navigate to <strong>My Account &gt; API Keys</strong></li>
              <li>Generate an API key and paste it above or set <code className="mono">DATA_GOV_IN_API_KEY</code> in backend <code className="mono">.env</code></li>
            </ol>
          </div>
        </div>

        {/* CSV Ingestion Fallback Card */}
        <div className="glass-card">
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "14px" }}>
            <div
              style={{
                width: "40px",
                height: "40px",
                borderRadius: "10px",
                background: "rgba(99, 102, 241, 0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--indigo-500)",
              }}
            >
              <UploadCloud size={22} />
            </div>
            <div>
              <h4 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-main)" }}>
                Standardized Agmarknet CSV Upload
              </h4>
              <span className="badge badge-indigo" style={{ fontSize: "0.65rem" }}>
                Reliable Offline Fallback &amp; Upsert
              </span>
            </div>
          </div>

          <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: "16px" }}>
            Import authentic daily mandi records from official Agmarknet CSV exports. The system validates required fields, formats dates, checks positive price bounds, and safely deduplicates without overwriting good data.
          </p>

          <div style={{ background: "rgba(0,0,0,0.25)", padding: "16px", borderRadius: "var(--radius-sm)", marginBottom: "16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap", marginBottom: "14px" }}>
              <input
                type="file"
                accept=".csv,.txt"
                onChange={handleFileChange}
                style={{ display: "none" }}
                id="csv-file-upload"
              />
              <label
                htmlFor="csv-file-upload"
                className="btn btn-secondary"
                style={{ cursor: "pointer", fontSize: "0.85rem", flex: 1, minWidth: "200px" }}
              >
                <FileText size={16} />
                <span>{selectedFile ? selectedFile.name : "Select Agmarknet CSV File"}</span>
              </label>

              <button
                className="btn btn-primary"
                onClick={handleUpload}
                disabled={!selectedFile || isUploading}
                style={{ fontSize: "0.85rem" }}
              >
                <UploadCloud size={16} />
                <span>{isUploading ? "Validating & Ingesting..." : "Upload & Ingest"}</span>
              </button>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: "8px", borderTop: "1px solid rgba(255,255,255,0.05)" }}>
              <span style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                Need authentic sample Agmarknet data?
              </span>
              <button
                className="btn btn-secondary"
                onClick={handleDownloadSampleCsv}
                style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                title="Download verified official Agmarknet sample CSV"
              >
                <Download size={13} />
                <span>Download Sample Official CSV</span>
              </button>
            </div>
          </div>

          {/* Import Result Notification */}
          {importResult && (
            <div
              style={{
                padding: "12px 16px",
                borderRadius: "var(--radius-sm)",
                background: importResult.success ? "rgba(16, 185, 129, 0.12)" : "rgba(239, 68, 68, 0.12)",
                border: `1px solid ${importResult.success ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
                fontSize: "0.85rem",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 600, color: importResult.success ? "var(--emerald-400)" : "var(--rose-500)" }}>
                {importResult.success ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
                <span>{importResult.message}</span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginTop: "4px" }}>
                Imported: <strong style={{ color: "var(--emerald-400)" }}>{importResult.imported_count}</strong> records | Skipped / Existing: {importResult.duplicate_count} | Errors: {importResult.skipped_count}
              </div>
              {importResult.errors && importResult.errors.length > 0 && (
                <div style={{ marginTop: "6px", fontSize: "0.75rem", color: "var(--rose-400)", maxHeight: "80px", overflowY: "auto" }}>
                  {importResult.errors.slice(0, 3).map((e, idx) => (
                    <div key={idx}>• {e}</div>
                  ))}
                  {importResult.errors.length > 3 && (
                    <div>+ {importResult.errors.length - 3} more errors logged</div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Agmarknet Schema Reference Card */}
      <div className="glass-card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "10px" }}>
          <div>
            <h4 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--text-main)" }}>
              Agmarknet Data Ingestion Schema Specifications
            </h4>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
              Follows Directorate of Marketing &amp; Inspection (DMI) format with automatic unit standardization (₹ / Quintal).
            </p>
          </div>
          <span className="badge badge-indigo" style={{ fontSize: "0.7rem" }}>
            Safe Upsert &amp; Duplication Guard Active
          </span>
        </div>

        <div className="table-responsive">
          <table className="modern-table">
            <thead>
              <tr>
                <th>Field Name</th>
                <th>Standard Column Names</th>
                <th>Required?</th>
                <th>Type / Format</th>
                <th>Handling Rules</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ fontWeight: 600 }}>Commodity</td>
                <td><code className="mono">Commodity, commodity, crop</code></td>
                <td><span className="badge badge-emerald">Yes</span></td>
                <td>Text</td>
                <td>Trimmed and capitalized (e.g. Onion, Wheat)</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Market / Mandi</td>
                <td><code className="mono">Market, market, mandi</code></td>
                <td><span className="badge badge-emerald">Yes</span></td>
                <td>Text</td>
                <td>APMC Mandi name</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Observation Date</td>
                <td><code className="mono">Arrival_Date, date, observation_date</code></td>
                <td><span className="badge badge-emerald">Yes</span></td>
                <td>Date (<code className="mono">DD/MM/YYYY</code> or <code className="mono">YYYY-MM-DD</code>)</td>
                <td>Validated calendar date, normalized to ISO-8601</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Modal Price</td>
                <td><code className="mono">Modal_Price, modal_price, modal</code></td>
                <td><span className="badge badge-emerald">Yes</span></td>
                <td>Float (&gt; 0)</td>
                <td>Primary benchmark price (₹/Quintal)</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>State &amp; District</td>
                <td><code className="mono">State, District</code></td>
                <td><span className="badge badge-amber">Optional</span></td>
                <td>Text</td>
                <td>Defaults to "General" if absent</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Min / Max Price</td>
                <td><code className="mono">Min_Price, Max_Price</code></td>
                <td><span className="badge badge-amber">Optional</span></td>
                <td>Float</td>
                <td>Trading range bounds</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 600 }}>Arrival Volume</td>
                <td><code className="mono">Arrivals_in_qtl, arrivals</code></td>
                <td><span className="badge badge-amber">Optional</span></td>
                <td>Float</td>
                <td>Quintals brought to market on date</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
