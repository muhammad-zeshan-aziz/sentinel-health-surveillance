import React, { useState, useEffect } from 'react';
import { X, ShieldCheck, PieChart, Users, Calendar, AlertTriangle, Layers } from 'lucide-react';
import { useFilters } from '../../context/FilterContext';

export const DrilldownDrawer = ({ isOpen, onClose, metricKey, metricTitle }) => {
  const { disease, districtPcode } = useFilters();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    const pcodeParam = districtPcode !== 'all' ? `&district_pcode=${districtPcode}` : '';
    const indicatorParam = metricKey || 'confirmed_cases';
    fetch(`/api/surveillance/drilldown?indicator=${indicatorParam}&disease=${disease}${pcodeParam}`)
      .then(res => res.json())
      .then(d => setData(d))
      .catch(err => console.error('Drilldown fetch error:', err))
      .finally(() => setLoading(false));
  }, [isOpen, metricKey, disease, districtPcode]);

  if (!isOpen) return null;

  const breakdowns = data?.breakdowns || {};
  const ageBands = breakdowns.age_band || [];
  const genderBreakdown = breakdowns.gender || [];
  const facilityBreakdown = breakdowns.facility || [];
  const testTypes = breakdowns.test_type || [];

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      <div 
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity" 
        onClick={onClose} 
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-white shadow-2xl flex flex-col">
          
          {/* Header */}
          <div className="p-5 border-b border-slate-200 bg-slate-50/80 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-teal-600" />
                <h3 className="text-base font-bold text-slate-900">Privacy-Safe Breakdown</h3>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                {metricTitle || 'Surveillance Indicator'} • {disease} • {districtPcode === 'all' ? 'All KP' : districtPcode}
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-5 space-y-6">
            {/* Zero-PII Notice */}
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3.5 flex items-start gap-3">
              <ShieldCheck className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div className="text-xs text-emerald-900 leading-relaxed">
                <span className="font-semibold block">HIPAA / CS619 Zero-PII Compliance</span>
                Patient demographic counts are presented in non-identifying aggregated age bands and test categories. No patient names, CNICs, or MRNs are stored or rendered.
              </div>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-16 text-slate-400 text-xs">
                Loading indicator records...
              </div>
            ) : data ? (
              <>
                {/* Total Sample */}
                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 flex justify-between items-center text-xs">
                  <span className="text-slate-600 font-medium">Underlying Sample Size:</span>
                  <span className="font-bold text-slate-900">{data.total_records?.toLocaleString()} verified records</span>
                </div>

                {/* Age Band Distribution */}
                {ageBands.length > 0 && (
                  <div>
                    <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                      <Users className="w-4 h-4 text-teal-600" />
                      Age Band Distribution
                    </h4>
                    <div className="space-y-2">
                      {ageBands.map((item, idx) => (
                        <div key={idx} className="text-xs">
                          <div className="flex justify-between font-medium text-slate-700 mb-1">
                            <span>Age {item.category}</span>
                            <span className="text-slate-500">{item.count} ({item.percentage}%)</span>
                          </div>
                          <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                            <div 
                              className="bg-teal-500 h-2 rounded-full transition-all duration-300"
                              style={{ width: `${Math.min(100, item.percentage)}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Gender Distribution */}
                {genderBreakdown.length > 0 && (
                  <div>
                    <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                      <PieChart className="w-4 h-4 text-indigo-600" />
                      Gender Ratio
                    </h4>
                    <div className="grid grid-cols-2 gap-3">
                      {genderBreakdown.map((item, idx) => (
                        <div key={idx} className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
                          <span className="text-xs text-slate-500 block">{item.category}</span>
                          <span className="text-lg font-bold text-slate-800">{item.count}</span>
                          <span className="text-[10px] text-slate-400 block">{item.percentage}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Test Types / Diagnostics */}
                {testTypes.length > 0 && (
                  <div>
                    <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                      <Layers className="w-4 h-4 text-amber-600" />
                      Diagnostic Test Methods
                    </h4>
                    <div className="space-y-1.5 text-xs">
                      {testTypes.map((t, idx) => (
                        <div key={idx} className="flex justify-between p-2 rounded bg-slate-50 border border-slate-100">
                          <span className="font-medium text-slate-700">{t.category}</span>
                          <span className="font-semibold text-slate-600">{t.count} ({t.percentage}%)</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Facility Distribution */}
                {facilityBreakdown.length > 0 && (
                  <div>
                    <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                      <Calendar className="w-4 h-4 text-emerald-600" />
                      Contributing Health Facilities
                    </h4>
                    <div className="border border-slate-200 rounded-xl overflow-hidden text-xs max-h-48 overflow-y-auto">
                      <table className="w-full text-left">
                        <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 sticky top-0">
                          <tr>
                            <th className="p-2 font-semibold">Facility</th>
                            <th className="p-2 font-semibold text-right">Volume</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {facilityBreakdown.map((f, i) => (
                            <tr key={i} className="hover:bg-slate-50">
                              <td className="p-2 font-medium text-slate-800 truncate max-w-[200px]" title={f.category}>
                                {f.category}
                              </td>
                              <td className="p-2 text-right text-slate-600 font-semibold">
                                {f.count}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="text-xs text-slate-500 text-center py-6">
                No granular drilldown records found for current criteria.
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-slate-200 bg-slate-50 flex justify-end">
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-100 transition"
            >
              Close Drawer
            </button>
          </div>

        </div>
      </div>
    </div>
  );
};
