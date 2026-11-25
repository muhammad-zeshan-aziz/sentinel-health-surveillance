import React from 'react';
import { 
  Menu, 
  Download, 
  UploadCloud, 
  Clock, 
  AlertCircle, 
  ShieldCheck,
  Calendar
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useFilters } from '../../context/FilterContext';

export const TopHeader = ({ activeTab, setActiveTab, setMobileOpen }) => {
  const { user } = useAuth();
  const { 
    disease, 
    districtPcode,
    timeSpan,
    caseStatus,
    lastRefreshed, 
    activeWarningsCount, 
    isSyntheticActive,
    refreshData 
  } = useFilters();

  const getTabTitle = () => {
    switch (activeTab) {
      case 'overview':
        return { title: 'Surveillance Overview', desc: 'Real-time epidemiological metrics, outbreak outlook & facility reporting completeness' };
      case 'hotspots':
        return { title: 'District Hotspots GIS', desc: 'Dual-layer Leaflet choropleth tracking observed clusters & 7-day forecast risk' };
      case 'alerts':
        return { title: 'Early Warning Queue', desc: 'CDC EARS anomaly detection, automated severity scoring & DHO incident review' };
      case 'labs':
        return { title: 'Hospital & Laboratory Ingestion', desc: 'Privacy-safe lab dropzone, episode deduplication & automated facility synchronization' };
      case 'reports':
        return { title: 'Model Governance & Reports', desc: 'Split-conformal ML evaluations, historical backtest logs & verifiable zero-PII exports' };
      default:
        return { title: 'Sentinel Platform', desc: 'Khyber Pakhtunkhwa Disease Surveillance' };
    }
  };

  const handleExport = async () => {
    try {
      const token = localStorage.getItem('sentinel_token');
      const pcodeParam = districtPcode !== 'all' ? `&district_pcode=${districtPcode}` : '';
      const spanParam = timeSpan ? `&time_span=${timeSpan}` : '';
      const statusParam = caseStatus !== 'all' ? `&case_status=${caseStatus}` : '';
      const url = `/api/reports/export?format=csv&disease=${disease}${pcodeParam}${spanParam}${statusParam}`;
      const res = await fetch(url, {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
      });
      if (res.ok) {
        const blob = await res.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `sentinel_${disease.toLowerCase()}_surveillance.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
      }
    } catch (e) {
      console.error('Export error:', e);
    }
  };

  const handleUploadCTA = () => {
    setActiveTab('labs');
  };

  const { title, desc } = getTabTitle();

  return (
    <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-md border-b border-slate-200 px-3 sm:px-6 py-2.5 sm:py-3 transition-all">
      <div className="flex flex-wrap items-center justify-between gap-2.5 sm:gap-3 min-w-0">
        {/* Left: Mobile hamburger + Active Screen Title */}
        <div className="flex items-center space-x-3 min-w-0">
          <button
            onClick={() => setMobileOpen(true)}
            className="lg:hidden p-2 text-slate-600 hover:text-slate-900 rounded-lg border border-slate-200 bg-slate-50 shrink-0"
            aria-label="Open sidebar"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight truncate">{title}</h2>
              
              {/* Prominent CS619 Provenance Badge with Interactive Tooltip */}
              {isSyntheticActive && (
                <div className="relative group inline-flex items-center shrink-0">
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300 shadow-2xs tracking-wider uppercase cursor-help transition hover:bg-amber-200">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>
                    <span>DEMO DATA: IDSR REAL + DEMO LABS</span>
                    <AlertCircle className="w-3 h-3 text-amber-700" />
                  </div>
                  
                  {/* Informative Provenance Popover */}
                  <div className="pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-200 absolute left-0 top-full mt-1.5 z-50 w-72 p-3 bg-slate-900 text-slate-100 text-[11px] rounded-xl shadow-xl border border-slate-700 leading-relaxed">
                    <div className="font-bold text-amber-300 border-b border-slate-700 pb-1 mb-1.5 flex items-center gap-1.5">
                      <ShieldCheck className="w-3.5 h-3.5 text-teal-400" />
                      <span>Data Provenance (CS619 Compliance)</span>
                    </div>
                    <p className="text-slate-300">
                      • <b>Surveillance & ML Forecasts:</b> Real weekly NIH IDSR KP 2023–2026 panel & official PBS 2023 Census population.
                    </p>
                    <p className="text-slate-300 mt-1">
                      • <b>Sentinel Hospital Feeds:</b> Calibrated synthetic diagnostic lab feeds across 70 facilities per CS619 pilot rules.
                    </p>
                  </div>
                </div>
              )}

              {/* Active Warning Counter Badge */}
              {activeWarningsCount > 0 && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-200 shrink-0">
                  <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping"></span>
                  {activeWarningsCount} Active Outbreak {activeWarningsCount === 1 ? 'Alert' : 'Alerts'}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 hidden sm:block mt-0.5 truncate">{desc}</p>
          </div>
        </div>

        {/* Right: Metadata + Quick Actions */}
        <div className="flex items-center flex-wrap gap-2 shrink-0">
          {/* Timestamp Indicator */}
          <div className="hidden 2xl:flex items-center gap-1.5 text-xs text-slate-500 bg-slate-100/80 px-2.5 py-1.5 rounded-lg border border-slate-200">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span>Refreshed: <span className="font-medium text-slate-700">{lastRefreshed}</span></span>
          </div>

          {/* Upload Demo Data CTA */}
          <button
            onClick={handleUploadCTA}
            className="inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 text-xs font-semibold rounded-lg bg-teal-50 text-teal-700 hover:bg-teal-100 border border-teal-200 transition"
          >
            <UploadCloud className="w-3.5 h-3.5 text-teal-600" />
            <span>Upload Lab Data</span>
          </button>

          {/* Export Action */}
          <button
            onClick={handleExport}
            className="inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-900 text-white hover:bg-slate-800 shadow-sm transition"
          >
            <Download className="w-3.5 h-3.5 text-slate-300" />
            <span>Export CSV</span>
          </button>
        </div>
      </div>
    </header>
  );
};
