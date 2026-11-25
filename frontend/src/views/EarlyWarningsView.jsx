import React, { useState, useEffect } from 'react';
import { 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  ShieldAlert, 
  Filter, 
  FileText, 
  UserCheck, 
  X, 
  Check, 
  Info,
  ChevronRight,
  Eye,
  Activity
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useFilters } from '../context/FilterContext';

export const EarlyWarningsView = () => {
  const { user, isDHO, switchRole } = useAuth();
  const { disease, districtPcode, refreshTrigger, refreshData } = useFilters();

  const [alerts, setAlerts] = useState([]);
  const [counts, setCounts] = useState({
    active_warnings: 0,
    priority_review_count: 0,
    watch_count: 0,
    acknowledged_count: 0,
    total_count: 0
  });
  const [loading, setLoading] = useState(true);
  const [filterTab, setFilterTab] = useState('active'); // 'all' | 'active' | 'priority' | 'watch' | 'acknowledged'

  // Modal State
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [reviewNotes, setReviewNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [actionSuccess, setActionSuccess] = useState('');
  const [actionError, setActionError] = useState('');

  // Fetch alerts
  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (disease) params.set('disease', disease);
    if (districtPcode && districtPcode !== 'all') params.set('district_pcode', districtPcode);

    if (filterTab === 'active') {
      params.set('acknowledged', 'false');
    } else if (filterTab === 'priority') {
      params.set('alert_level', 'priority_review');
      params.set('acknowledged', 'false');
    } else if (filterTab === 'watch') {
      params.set('alert_level', 'watch');
      params.set('acknowledged', 'false');
    } else if (filterTab === 'acknowledged') {
      params.set('acknowledged', 'true');
    }

    fetch(`/api/alerts/queue?${params.toString()}`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load early warnings`);
        return res.json();
      })
      .then(data => {
        if (Array.isArray(data?.alerts)) {
          setAlerts(data.alerts);
          setCounts({
            active_warnings: data.total_active_warnings ?? 0,
            priority_review_count: data.priority_review_count ?? 0,
            watch_count: data.watch_count ?? 0,
            acknowledged_count: data.acknowledged_count ?? 0,
            total_count: (data.total_active_warnings ?? 0) + (data.acknowledged_count ?? 0)
          });
        } else {
          setAlerts([]);
        }
      })
      .catch(err => {
        console.error('Alert queue error:', err);
        setAlerts([]);
      })
      .finally(() => setLoading(false));
  }, [disease, districtPcode, filterTab, refreshTrigger]);

  const handleOpenReview = (alert) => {
    setSelectedAlert(alert);
    setReviewNotes(alert?.review_notes || '');
    setActionSuccess('');
    setActionError('');
  };

  const handleAcknowledge = async () => {
    if (!selectedAlert) return;
    setSubmitting(true);
    setActionError('');
    setActionSuccess('');

    try {
      const token = localStorage.getItem('sentinel_token');
      const res = await fetch(`/api/alerts/${selectedAlert.id}/acknowledge`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify({ 
          review_notes: reviewNotes.trim() || 'Reviewed and confirmed by District Health Officer (DHO).' 
        })
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Failed to acknowledge alert');
      }

      const resData = await res.json();
      setActionSuccess(resData.message || 'Alert successfully acknowledged and logged to provincial registry.');
      
      // Update local state immediately for instant UX responsiveness
      setAlerts(prev => prev.map(a => a.id === selectedAlert.id ? {
        ...a,
        acknowledged: true,
        acknowledged_by: user?.username || 'dho_kp',
        review_notes: reviewNotes || 'Reviewed and confirmed'
      } : a));

      // Trigger global synchronization for header/sidebar badges
      refreshData();

      setTimeout(() => {
        setSelectedAlert(null);
      }, 1100);
    } catch (err) {
      setActionError(err.message || 'An error occurred during alert acknowledgment');
    } finally {
      setSubmitting(false);
    }
  };

  const getSeverityBadge = (level) => {
    switch (level) {
      case 'priority_review':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-100 text-rose-800 border border-rose-300 shadow-2xs">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-600 animate-pulse"></span>
            Priority Review
          </span>
        );
      case 'watch':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
            Watch Alert
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-700">
            Routine
          </span>
        );
    }
  };

  const FILTER_PILLS = [
    { key: 'active', label: 'Unacknowledged', count: counts.active_warnings, color: 'text-rose-700', activeBg: 'bg-rose-50 border-rose-300 ring-2 ring-rose-500/20' },
    { key: 'priority', label: 'Priority Review', count: counts.priority_review_count, color: 'text-rose-900', activeBg: 'bg-rose-50 border-rose-300 ring-2 ring-rose-500/20' },
    { key: 'watch', label: 'Watch Alerts', count: counts.watch_count, color: 'text-amber-800', activeBg: 'bg-amber-50 border-amber-300 ring-2 ring-amber-500/20' },
    { key: 'all', label: 'All Alerts', count: counts.total_count || alerts.length, color: 'text-slate-800', activeBg: 'bg-teal-50 border-teal-300 ring-2 ring-teal-500/20' },
    { key: 'acknowledged', label: 'Acknowledged', count: counts.acknowledged_count, color: 'text-emerald-800', activeBg: 'bg-emerald-50 border-emerald-300 ring-2 ring-emerald-500/20' },
  ];

  return (
    <div className="space-y-6">
      
      {/* 1. Header Banner & Counter Cards (All 5 Severity / Status Categories) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 sm:gap-4">
        {FILTER_PILLS.map((pill) => {
          const isActive = filterTab === pill.key;
          return (
            <button
              key={pill.key}
              onClick={() => setFilterTab(pill.key)}
              className={`p-3.5 sm:p-4 rounded-xl border text-left cursor-pointer transition-all ${
                isActive 
                  ? pill.activeBg 
                  : 'bg-white border-slate-200 hover:border-slate-300 shadow-2xs'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className={`text-[11px] font-bold uppercase tracking-wider ${pill.color}`}>
                  {pill.label}
                </span>
                {pill.key === 'priority' && <ShieldAlert className="w-4 h-4 text-rose-600" />}
                {pill.key === 'watch' && <Clock className="w-4 h-4 text-amber-600" />}
                {pill.key === 'active' && <AlertTriangle className="w-4 h-4 text-rose-600" />}
                {pill.key === 'all' && <FileText className="w-4 h-4 text-slate-500" />}
                {pill.key === 'acknowledged' && <CheckCircle2 className="w-4 h-4 text-emerald-600" />}
              </div>
              <div className="text-2xl font-bold text-slate-900 mt-1.5">{pill.count}</div>
              <p className="text-[10px] text-slate-400 mt-0.5 truncate">
                {pill.key === 'active' && 'Immediate DHO triage'}
                {pill.key === 'priority' && 'EARS + Forecast breach'}
                {pill.key === 'watch' && 'Early deviation watch'}
                {pill.key === 'all' && `${disease} incident log`}
                {pill.key === 'acknowledged' && 'Formal audit records'}
              </p>
            </button>
          );
        })}
      </div>

      {/* 2. Main Alert Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3 bg-slate-50/50">
          <div>
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-teal-600" />
              CDC EARS Aberration Queue & Outbreak Verification
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Weekly C1 (7-week), C2 (2-week guardbanded), and C3 cumulative excess signals with conformal forecast validation.
            </p>
          </div>

          {/* Quick Segmented Severity Filter Pills */}
          <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-lg border border-slate-200 text-xs overflow-x-auto">
            {FILTER_PILLS.map((p) => (
              <button
                key={p.key}
                onClick={() => setFilterTab(p.key)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition shrink-0 ${
                  filterTab === p.key
                    ? 'bg-white text-slate-900 shadow-2xs font-bold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {p.label} ({p.count})
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 font-semibold">
              <tr>
                <th className="p-3">District & Division</th>
                <th className="p-3">Disease & Week</th>
                <th className="p-3 text-center">Observed Cases vs Baseline</th>
                <th className="p-3 text-center">EARS Scores (Z₁, Z₂, C₃)</th>
                <th className="p-3 text-center">Forecast Breach</th>
                <th className="p-3 text-center">Severity</th>
                <th className="p-3 text-center">Status</th>
                <th className="p-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-slate-400">
                    <div className="flex items-center justify-center gap-2">
                      <Clock className="w-4 h-4 animate-spin text-teal-600" />
                      <span>Loading outbreak alert queue...</span>
                    </div>
                  </td>
                </tr>
              ) : alerts.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-slate-400">
                    <AlertTriangle className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    <p className="font-semibold text-slate-600">No outbreak alerts found matching current filter criteria.</p>
                    <p className="text-[11px] text-slate-400 mt-1">Try selecting "All Alerts" or toggling the disease filter in the top bar.</p>
                  </td>
                </tr>
              ) : (
                alerts.map((alert) => (
                  <tr key={alert.id} className="hover:bg-slate-50/80 transition">
                    <td className="p-3">
                      <div className="font-bold text-slate-900">{alert.district_name || 'District'}</div>
                      <div className="text-[10px] text-slate-400 font-mono">
                        {alert.district_pcode} • {alert.division || 'Khyber Pakhtunkhwa'}
                      </div>
                    </td>

                    <td className="p-3">
                      <span className="font-semibold text-slate-800">{alert.disease}</span>
                      <div className="text-[10px] text-slate-500">{alert.year}-W{String(alert.epi_week).padStart(2, '0')}</div>
                    </td>

                    <td className="p-3 text-center">
                      <div className="font-bold text-slate-900">
                        {alert.cases_observed != null 
                          ? `${Number(alert.cases_observed).toLocaleString()} cases` 
                          : `${Number(alert.incidence_per_100k ?? 0).toFixed(1)} / 100k`}
                      </div>
                      <div className="text-[10px] text-slate-500">
                        {alert.baseline_mean != null 
                          ? `Baseline: ${Number(alert.baseline_mean).toFixed(1)}` 
                          : `Incidence: ${Number(alert.incidence_per_100k ?? 0).toFixed(1)}`}
                      </div>
                    </td>

                    <td className="p-3 text-center font-mono">
                      <div className="text-slate-700 font-semibold">
                        {Number(alert.ears_c1_score ?? 0).toFixed(1)} / {Number(alert.ears_c2_score ?? 0).toFixed(1)} / {Number(alert.ears_c3_score ?? 0).toFixed(1)}
                      </div>
                      <div className="text-[9px] text-slate-400">Threshold: Z &gt; 2.0</div>
                    </td>

                    <td className="p-3 text-center">
                      {alert.forecast_breach ? (
                        <span className="inline-flex px-2 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-200">
                          Yes (Surge)
                        </span>
                      ) : (
                        <span className="text-slate-400 text-[11px]">—</span>
                      )}
                    </td>

                    <td className="p-3 text-center">
                      {getSeverityBadge(alert.alert_level)}
                    </td>

                    <td className="p-3 text-center">
                      {alert.acknowledged ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                          <Check className="w-3 h-3" />
                          Ack by {alert.acknowledged_by || 'DHO'}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
                          <Clock className="w-3 h-3" />
                          Pending Review
                        </span>
                      )}
                    </td>

                    <td className="p-3 text-right">
                      <button
                        onClick={() => handleOpenReview(alert)}
                        className={`px-3 py-1.5 text-xs font-semibold rounded-lg border transition ${
                          alert.acknowledged
                            ? 'bg-slate-50 text-slate-600 hover:bg-slate-100 border-slate-200'
                            : 'bg-teal-50 text-teal-700 hover:bg-teal-100 border-teal-200 font-bold'
                        }`}
                      >
                        {alert.acknowledged ? 'View Audit' : 'Review & Action'}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 3. Review & Acknowledgment Modal */}
      {selectedAlert && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs">
          <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-teal-600 block">
                  Incident Review & Verification
                </span>
                <h3 className="text-base font-bold text-slate-900">
                  {selectedAlert.district_name || 'District'} ({selectedAlert.disease})
                </h3>
                <p className="text-xs text-slate-500">
                  Week {selectedAlert.year}-W{String(selectedAlert.epi_week).padStart(2, '0')} • Alert ID #{selectedAlert.id}
                </p>
              </div>
              <button
                onClick={() => setSelectedAlert(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 space-y-4 text-xs">
              
              {/* Alert Metrics Pill Box */}
              <div className="grid grid-cols-3 gap-2 bg-slate-50 p-3 rounded-xl border border-slate-200 text-center">
                <div>
                  <span className="text-slate-500 text-[10px] block">Observed Load</span>
                  <span className="font-bold text-base text-slate-900">
                    {selectedAlert.cases_observed != null 
                      ? `${Number(selectedAlert.cases_observed).toLocaleString()} cases` 
                      : `${Number(selectedAlert.incidence_per_100k ?? 0).toFixed(1)} / 100k`}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block">Baseline / Score</span>
                  <span className="font-bold text-base text-slate-900">
                    {selectedAlert.baseline_mean != null 
                      ? Number(selectedAlert.baseline_mean).toFixed(1) 
                      : `Z: ${Number(selectedAlert.composite_score ?? 0).toFixed(2)}`}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block">Severity Tier</span>
                  <div className="mt-0.5">{getSeverityBadge(selectedAlert.alert_level)}</div>
                </div>
              </div>

              {/* Headline & Details */}
              {selectedAlert.headline && (
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="text-[10px] font-bold text-slate-500 uppercase block mb-0.5">Surveillance Synopsis:</span>
                  <p className="font-semibold text-slate-800">{selectedAlert.headline}</p>
                  {selectedAlert.details && (
                    <p className="text-slate-600 mt-1 leading-relaxed">{selectedAlert.details}</p>
                  )}
                </div>
              )}

              {/* Aberration Diagnostics Box */}
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl space-y-1 text-slate-700">
                <div className="font-bold text-amber-900 flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  Statistical Aberration Breakdown
                </div>
                <div>• Weekly C1 Z-score: <b>{Number(selectedAlert.ears_c1_score ?? 0).toFixed(2)}</b> (7-week moving baseline)</div>
                <div>• Weekly C2 Z-score: <b>{Number(selectedAlert.ears_c2_score ?? 0).toFixed(2)}</b> (2-week guardbanded)</div>
                <div>• Weekly C3 Cumulative: <b>{Number(selectedAlert.ears_c3_score ?? 0).toFixed(2)}</b> (excess trajectory)</div>
                <div>• Composite Aberration Score: <b>{Number(selectedAlert.composite_score ?? 0).toFixed(2)}</b></div>
              </div>

              {/* RBAC Verification Alert */}
              {!isDHO && !selectedAlert.acknowledged && (
                <div className="p-3 bg-blue-50 border border-blue-200 rounded-xl text-blue-900 flex items-start gap-2.5">
                  <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold block">Role-Based Access Control Notice (CS619)</span>
                    You are signed in as <b>{user?.title || user?.role || 'User'}</b>. Formal acknowledgment requires District Health Officer (DHO) authorization.
                    <button
                      onClick={() => switchRole('dho_kp')}
                      className="mt-1.5 block text-teal-700 font-bold underline hover:text-teal-900"
                    >
                      1-Click Switch to DHO Persona (dho_kp)
                    </button>
                  </div>
                </div>
              )}

              {/* DHO Notes Field */}
              <div>
                <label className="font-bold text-slate-700 block mb-1">
                  Public Health Action / Incident Notes:
                </label>
                <textarea
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  disabled={!isDHO || selectedAlert.acknowledged}
                  placeholder="Record rapid response team deployment, RDT kit dispatch, or local validation notes..."
                  rows={3}
                  className="w-full p-2.5 border border-slate-300 rounded-xl text-xs focus:ring-2 focus:ring-teal-500 focus:outline-none disabled:bg-slate-100 disabled:text-slate-500"
                />
              </div>

              {/* Action Success / Error Messages */}
              {actionSuccess && (
                <div className="p-2.5 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-lg font-semibold flex items-center gap-1.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>{actionSuccess}</span>
                </div>
              )}
              {actionError && (
                <div className="p-2.5 bg-rose-50 text-rose-800 border border-rose-200 rounded-lg font-semibold flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                  <span>{actionError}</span>
                </div>
              )}

            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
              <span className="text-[11px] text-slate-500">
                Audited to provincial health surveillance registry
              </span>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setSelectedAlert(null)}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white font-medium text-slate-700 hover:bg-slate-100"
                >
                  Close
                </button>

                {!selectedAlert.acknowledged && (
                  <button
                    onClick={handleAcknowledge}
                    disabled={!isDHO || submitting}
                    className="px-4 py-1.5 rounded-lg bg-teal-600 text-white font-semibold hover:bg-teal-700 disabled:opacity-50 flex items-center gap-1.5 transition"
                  >
                    {submitting ? 'Submitting...' : 'Confirm Acknowledgment'}
                  </button>
                )}
              </div>
            </div>

          </div>
        </div>
      )}

    </div>
  );
};
