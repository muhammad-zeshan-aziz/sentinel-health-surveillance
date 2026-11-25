import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  AlertTriangle, 
  CheckCircle, 
  Building2, 
  TrendingUp, 
  FileText, 
  Calendar,
  AlertCircle,
  Eye,
  ShieldAlert
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  ComposedChart, 
  Line, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend 
} from 'recharts';
import { useFilters } from '../context/FilterContext';
import { KPICard } from '../components/common/KPICard';
import { DrilldownDrawer } from '../components/common/DrilldownDrawer';

export const OverviewView = () => {
  const { 
    disease, 
    districtPcode, 
    facilityId, 
    timeSpan, 
    caseStatus,
    refreshTrigger 
  } = useFilters();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Drilldown Drawer State
  const [drilldownOpen, setDrilldownOpen] = useState(false);
  const [selectedIndicator, setSelectedIndicator] = useState('confirmed_cases');
  const [indicatorTitle, setIndicatorTitle] = useState('Confirmed Cases');

  useEffect(() => {
    setLoading(true);
    setError(null);

    const params = new URLSearchParams();
    params.set('disease', disease);
    if (districtPcode !== 'all') params.set('district_pcode', districtPcode);
    if (facilityId !== 'all') params.set('facility_id', facilityId);
    if (caseStatus !== 'all') params.set('case_status', caseStatus);
    if (timeSpan) params.set('time_span', timeSpan);

    fetch(`/api/surveillance/overview?${params.toString()}`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load overview`);
        return res.json();
      })
      .then(json => {
        setData(json);
      })
      .catch(err => {
        console.error('Overview error:', err);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }, [disease, districtPcode, facilityId, caseStatus, timeSpan, refreshTrigger]);

  const handleKPIClick = (indicatorKey, title) => {
    setSelectedIndicator(indicatorKey);
    setIndicatorTitle(title);
    setDrilldownOpen(true);
  };

  // Trends from backend already aligned with timeSpan and include forward forecast
  const trends = data?.trends || [];

  // Locate the index of the forward forecast point (Outlook)
  const forecastIdx = trends.findIndex(pt => pt.predicted_mean != null);

  // Find the last valid observed point index before the forecast point
  let lastObservedIdx = -1;
  let lastObservedVal = null;
  for (let i = (forecastIdx >= 0 ? forecastIdx - 1 : trends.length - 1); i >= 0; i--) {
    if (trends[i]?.reported_cases != null && !trends[i]?.is_missing) {
      lastObservedIdx = i;
      lastObservedVal = trends[i].reported_cases;
      break;
    }
  }

  const chartData = trends.map((pt, idx) => {
    const isForecast = pt.predicted_mean != null;
    const isBridge = idx === lastObservedIdx && forecastIdx >= 0;

    // Dashed forecast line: starts at the last observed week and extends to the forecast week
    let forecastLineVal = null;
    if (isForecast) {
      forecastLineVal = pt.predicted_mean;
    } else if (isBridge) {
      forecastLineVal = pt.reported_cases;
    }

    // Shaded 95% uncertainty band: opens up from the last observed point to [ci_lower, ci_upper]
    let ciRange = null;
    if (isForecast && pt.ci_lower_95 != null && pt.ci_upper_95 != null) {
      ciRange = [pt.ci_lower_95, pt.ci_upper_95];
    } else if (isBridge && lastObservedVal != null) {
      ciRange = [lastObservedVal, lastObservedVal];
    }

    return {
      ...pt,
      display_cases: pt.is_missing ? null : pt.reported_cases,
      forecast_line: forecastLineVal,
      ci_range: ciRange
    };
  });

  const kpis = data?.kpis || {
    confirmed_cases: 0,
    suspected_cases: 0,
    total_cases: 0,
    total_tests: 0,
    positivity_rate: 0,
    active_warnings: 0,
    reporting_coverage_pct: 0,
    confirmed_delta_pct: null,
    suspected_delta_pct: null,
    total_delta_pct: null,
    coverage_delta_pct: null
  };

  return (
    <div className="space-y-6">
      
      {/* 1. Top KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <KPICard
          title="Confirmed Cases"
          value={loading ? '...' : kpis.confirmed_cases?.toLocaleString()}
          subtitle="Microscopy / PCR Verified"
          change={kpis.confirmed_delta_pct !== null && kpis.confirmed_delta_pct !== undefined ? `${kpis.confirmed_delta_pct > 0 ? '+' : ''}${kpis.confirmed_delta_pct}%` : undefined}
          changeType={kpis.confirmed_delta_pct > 0 ? 'increase' : kpis.confirmed_delta_pct < 0 ? 'decrease' : 'neutral'}
          goodDirection="down"
          icon={CheckCircle}
          colorScheme="teal"
          onClick={() => handleKPIClick('confirmed_cases', 'Confirmed Cases')}
        />
        <KPICard
          title="Suspected Cases"
          value={loading ? '...' : kpis.suspected_cases?.toLocaleString()}
          subtitle="Syndromic Presentations"
          change={kpis.suspected_delta_pct !== null && kpis.suspected_delta_pct !== undefined ? `${kpis.suspected_delta_pct > 0 ? '+' : ''}${kpis.suspected_delta_pct}%` : undefined}
          changeType={kpis.suspected_delta_pct > 0 ? 'increase' : kpis.suspected_delta_pct < 0 ? 'decrease' : 'neutral'}
          goodDirection="down"
          icon={Activity}
          colorScheme="indigo"
          onClick={() => handleKPIClick('suspected_cases', 'Suspected Cases')}
        />
        <KPICard
          title="Diagnostic Volume"
          value={loading ? '...' : kpis.total_tests?.toLocaleString()}
          subtitle={`Positivity: ${kpis.positivity_rate || 0}%`}
          badgeText={`${kpis.positivity_rate}% Pos`}
          icon={FileText}
          colorScheme="amber"
          onClick={() => handleKPIClick('total_tests', 'Diagnostic Test Volume')}
        />
        <KPICard
          title="Active Warnings"
          value={loading ? '...' : kpis.active_warnings}
          subtitle="CDC EARS Aberrations"
          badgeText={kpis.active_warnings > 0 ? `${kpis.active_warnings} Action Req` : 'Normal'}
          changeType={kpis.active_warnings > 0 ? 'increase' : 'neutral'}
          icon={AlertTriangle}
          colorScheme="rose"
          onClick={() => handleKPIClick('active_warnings', 'EARS Outbreak Alerts')}
        />
        <KPICard
          title="Reporting Completeness"
          value={loading ? '...' : `${kpis.reporting_coverage_pct}%`}
          subtitle="70 Sentinel Hospitals"
          change={kpis.coverage_delta_pct !== null && kpis.coverage_delta_pct !== undefined ? `${kpis.coverage_delta_pct > 0 ? '+' : ''}${kpis.coverage_delta_pct}%` : undefined}
          changeType={kpis.coverage_delta_pct > 0 ? 'increase' : kpis.coverage_delta_pct < 0 ? 'decrease' : 'neutral'}
          goodDirection="up"
          icon={Building2}
          colorScheme="emerald"
          onClick={() => handleKPIClick('reporting_coverage', 'Sentinel Reporting Timeliness')}
        />
      </div>

      {/* 2. Main Epidemiological Trend & 7-Day Outlook Chart */}
      <div className="bg-white rounded-xl border border-slate-200/90 p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 gap-3">
          <div>
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-teal-600" />
              Epidemiological Trend & 7-Day Forward Forecast (t+1)
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Weekly historical incidence with split-conformal 95% calibrated prediction intervals. Distinguishes missing weeks (NR) from true zero counts.
            </p>
          </div>

          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-teal-600 inline-block"></span>
              <span className="text-slate-600 font-medium">Observed Cases</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-amber-500 inline-block border-t-2 border-dashed border-amber-500"></span>
              <span className="text-slate-600 font-medium">ML Forecast (t+1)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded bg-amber-100 border border-amber-300 inline-block"></span>
              <span className="text-slate-600 font-medium">95% Uncertainty Band</span>
            </div>
          </div>
        </div>

        {/* Chart Canvas */}
        <div className="h-80 w-full pt-4">
          {loading ? (
            <div className="h-full flex items-center justify-center text-slate-400 text-xs">
              Loading epidemiological time-series...
            </div>
          ) : chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis 
                  dataKey="label" 
                  tick={{ fontSize: 11, fill: '#64748b' }} 
                  dy={8}
                />
                <YAxis 
                  tick={{ fontSize: 11, fill: '#64748b' }} 
                  dx={-5}
                />
                <Tooltip 
                  content={({ active, payload, label }) => {
                    if (active && payload && payload.length) {
                      const pt = payload[0].payload;
                      const hasForecast = pt.predicted_mean != null;
                      return (
                        <div className="bg-slate-900 text-white p-3 rounded-xl text-xs shadow-xl border border-slate-700 min-w-[210px]">
                          <div className="font-bold border-b border-slate-700 pb-1 mb-1.5 text-teal-300 flex items-center justify-between">
                            <span>Week {label}</span>
                            {hasForecast && (
                              <span className="text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded border border-amber-500/30 font-semibold">
                                ML Outlook
                              </span>
                            )}
                          </div>
                          {pt.is_missing ? (
                            <div className="text-amber-400 font-semibold mb-1">
                              ⚠️ Report Missing / Not Received (NR)
                            </div>
                          ) : pt.reported_cases != null ? (
                            <div className="flex justify-between py-0.5">
                              <span className="text-slate-400">Observed Cases:</span>
                              <span className="font-bold text-white">{Number(pt.reported_cases).toLocaleString()}</span>
                            </div>
                          ) : null}

                          {hasForecast && (
                            <div className="flex justify-between py-0.5 text-amber-300 font-bold border-t border-slate-800 mt-1 pt-1">
                              <span>Model Forecast:</span>
                              <span>{Number(pt.predicted_mean).toLocaleString()} cases</span>
                            </div>
                          )}

                          {pt.ci_lower_95 != null && pt.ci_upper_95 != null && (
                            <div className="mt-1 pt-1 border-t border-slate-800 space-y-0.5">
                              <div className="flex justify-between text-slate-300 text-[11px]">
                                <span>95% Conformal Band:</span>
                                <span className="font-mono font-semibold text-amber-200">
                                  [{Number(pt.ci_lower_95).toLocaleString()} – {Number(pt.ci_upper_95).toLocaleString()}]
                                </span>
                              </div>
                              <div className="flex justify-between text-slate-400 text-[10px]">
                                <span>Uncertainty Margin:</span>
                                <span>±{Math.round((pt.ci_upper_95 - pt.ci_lower_95) / 2).toLocaleString()} cases</span>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                
                {/* 95% Conformal Prediction Interval Shaded Band */}
                <Area 
                  type="monotone" 
                  dataKey="ci_range" 
                  fill="#fef3c7" 
                  stroke="#f59e0b" 
                  strokeDasharray="3 3"
                  strokeWidth={1.5}
                  fillOpacity={0.5} 
                  name="95% Uncertainty Band"
                  connectNulls={false}
                />

                {/* Historical Observed Cases Line (Teal) */}
                <Line 
                  type="monotone" 
                  dataKey="display_cases" 
                  stroke="#0D9488" 
                  strokeWidth={2.5} 
                  dot={{ r: 3, fill: '#0D9488' }} 
                  activeDot={{ r: 6 }} 
                  name="Observed Cases"
                  connectNulls={false}
                />

                {/* Bridged Forecast Line for t+1 (Dashed Orange) */}
                <Line 
                  type="monotone" 
                  dataKey="forecast_line" 
                  stroke="#F59E0B" 
                  strokeWidth={2.5} 
                  strokeDasharray="4 4"
                  dot={{ r: 4, fill: '#F59E0B' }} 
                  activeDot={{ r: 6 }}
                  name="Forecast (t+1)"
                  connectNulls={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-400 text-xs">
              No surveillance observations available for selected filters.
            </div>
          )}
        </div>
      </div>

      {/* 3. Bottom Row: District Watch Cards + Hospital Reporting Table */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* District Watch Spotlight (1 Col) */}
        <div className="bg-white rounded-xl border border-slate-200/90 p-5 shadow-xs flex flex-col">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                <AlertCircle className="w-4 h-4 text-amber-500" />
                District Watch Spotlight
              </h3>
              <p className="text-xs text-slate-500">Highest incidence & surge priority</p>
            </div>
            <span className="text-[10px] font-semibold text-teal-700 bg-teal-50 px-2 py-0.5 rounded-full border border-teal-200">
              Live Monitor
            </span>
          </div>

          <div className="divide-y divide-slate-100 flex-1 overflow-y-auto mt-2">
            {(data?.district_watch || []).slice(0, 5).map((item) => {
              const isSurge = (item.percent_change || 0) > 0;
              return (
                <div key={item.district_pcode} className="py-3 flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-800 text-xs">{item.district_name}</span>
                      <span className="text-[10px] text-slate-400 font-mono">({item.district_pcode})</span>
                    </div>
                    <div className="text-[11px] text-slate-500 mt-0.5">
                      Incidence: <span className="font-medium text-slate-700">{item.incidence_per_100k} / 100k</span> • {item.division}
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="text-xs font-bold text-slate-900 block">
                      {item.cases_latest?.toLocaleString()} cases
                    </span>
                    <span className={`text-[10px] font-semibold flex items-center justify-end gap-0.5 ${
                      isSurge ? 'text-rose-600' : 'text-emerald-600'
                    }`}>
                      {isSurge ? '+' : ''}{item.percent_change}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Hospital Reporting Completeness (2 Cols) */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200/90 p-5 shadow-xs flex flex-col">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                <Building2 className="w-4 h-4 text-teal-600" />
                Sentinel Hospital Reporting Timeliness & Completeness
              </h3>
              <p className="text-xs text-slate-500">70 District Headquarters, Tehsil & Teaching Hospitals in Khyber Pakhtunkhwa</p>
            </div>
            <span className="text-xs text-slate-500">
              Coverage: <span className="font-bold text-slate-800">{kpis.reporting_coverage_pct}%</span>
            </span>
          </div>

          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 border-b border-slate-200">
                <tr>
                  <th className="p-2.5 font-semibold">Hospital / Facility</th>
                  <th className="p-2.5 font-semibold">District</th>
                  <th className="p-2.5 font-semibold text-center">Submitted / Expected</th>
                  <th className="p-2.5 font-semibold text-center">Completeness</th>
                  <th className="p-2.5 font-semibold text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(data?.hospital_reporting || []).slice(0, 6).map((fac) => {
                  const isMissing = fac.has_missing_report || fac.completeness_pct < 80;
                  return (
                    <tr key={fac.facility_id} className="hover:bg-slate-50/80 transition">
                      <td className="p-2.5 font-medium text-slate-900 truncate max-w-[220px]">
                        {fac.facility_name}
                      </td>
                      <td className="p-2.5 text-slate-600">
                        {fac.district_name}
                      </td>
                      <td className="p-2.5 text-center text-slate-600 font-mono">
                        {fac.reports_submitted} / {fac.reports_expected}
                      </td>
                      <td className="p-2.5 text-center">
                        <div className="flex items-center justify-center gap-2">
                          <div className="w-16 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                            <div 
                              className={`h-1.5 rounded-full ${
                                fac.completeness_pct >= 90 ? 'bg-emerald-500' : fac.completeness_pct >= 75 ? 'bg-amber-500' : 'bg-rose-500'
                              }`}
                              style={{ width: `${Math.min(100, fac.completeness_pct)}%` }}
                            />
                          </div>
                          <span className="font-semibold text-slate-700">{fac.completeness_pct}%</span>
                        </div>
                      </td>
                      <td className="p-2.5 text-right">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                          !isMissing
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-rose-50 text-rose-700 border border-rose-200'
                        }`}>
                          {!isMissing ? 'Timely' : 'Delayed / Missing'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

      </div>

      {/* Drilldown Drawer for Privacy-Safe Details */}
      <DrilldownDrawer
        isOpen={drilldownOpen}
        onClose={() => setDrilldownOpen(false)}
        metricKey={selectedIndicator}
        metricTitle={indicatorTitle}
      />

    </div>
  );
};
