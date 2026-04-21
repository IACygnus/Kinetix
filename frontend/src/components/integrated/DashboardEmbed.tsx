/**
 * DashboardEmbed — Renders the full Dashboard component in embedded/read-only mode.
 * Used inside IntegratedReportPage to show the same report view as the standalone dashboard.
 * HF9.3-B: Dashboard.tsx now hides its footer when embedded=true (no CSS hack needed).
 */
import Dashboard from '../dashboard/Dashboard';

interface DashboardEmbedProps {
  executionId: string;
}

export default function DashboardEmbed({ executionId }: DashboardEmbedProps) {
  return (
    <div className="border-b-2 pb-4 mb-4" style={{ borderColor: '#f5a623' }}>
      <Dashboard
        executionId={executionId}
        onLogout={() => {}}
        onBack={() => {}}
        embedded={true}
      />
    </div>
  );
}
