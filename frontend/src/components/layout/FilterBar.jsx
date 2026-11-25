import React from 'react';
import { 
  Filter, 
  RotateCcw, 
  Calendar, 
  Layers, 
  Building, 
  CheckCircle2,
  Bug
} from 'lucide-react';
import { useFilters } from '../../context/FilterContext';

export const FilterBar = () => {
  const {
    disease,
    setDisease,
    districtPcode,
    setDistrictPcode,
    facilityId,
    setFacilityId,
    timeSpan,
    setTimeSpan,
    caseStatus,
    setCaseStatus,
    districts,
    facilities,
    resetFilters
  } = useFilters();

  return (
    <div className="bg-white border-b border-slate-200 px-3 sm:px-6 py-2 shadow-2xs">
      <div className="flex flex-wrap items-center justify-between gap-2 sm:gap-3 text-xs min-w-0">
        
        {/* Left: Filter Selectors */}
        <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 min-w-0">
          <div className="flex items-center gap-1 text-slate-600 font-semibold uppercase tracking-wider text-[11px] mr-0.5 shrink-0">
            <Filter className="w-3.5 h-3.5 text-teal-600" />
            <span>Filters:</span>
          </div>

          {/* 1. Disease Switcher */}
          <div className="relative shrink-0">
            <select
              value={disease}
              onChange={(e) => setDisease(e.target.value)}
              className="appearance-none bg-slate-50 hover:bg-slate-100 text-slate-800 font-semibold px-2.5 py-1.5 pr-6 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-teal-500 text-xs transition cursor-pointer"
            >
              <option value="Malaria">Malaria</option>
              <option value="Typhoid">Typhoid</option>
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-1.5 text-slate-500 text-[10px]">
              ▼
            </div>
          </div>

          {/* 2. District Filter (35 KP districts) */}
          <div className="relative shrink-0">
            <select
              value={districtPcode}
              onChange={(e) => {
                setDistrictPcode(e.target.value);
                setFacilityId('all'); // Reset facility when district changes
              }}
              className="appearance-none bg-slate-50 hover:bg-slate-100 text-slate-800 font-medium px-2.5 py-1.5 pr-6 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-teal-500 text-xs transition max-w-[150px] sm:max-w-[170px] truncate cursor-pointer"
            >
              <option value="all">All KP Districts (35)</option>
              {Array.isArray(districts) && districts.map((d) => {
                const pcode = d.district_pcode || d.pcode || '';
                const name = d.district_name || d.name || 'Unnamed District';
                return (
                  <option key={pcode} value={pcode}>
                    {name} ({pcode})
                  </option>
                );
              })}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-1.5 text-slate-500 text-[10px]">
              ▼
            </div>
          </div>

          {/* 3. Hospital / Facility Filter */}
          <div className="relative shrink-0">
            <select
              value={facilityId}
              onChange={(e) => setFacilityId(e.target.value)}
              className="appearance-none bg-slate-50 hover:bg-slate-100 text-slate-800 font-medium px-2.5 py-1.5 pr-6 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-teal-500 text-xs transition max-w-[160px] sm:max-w-[190px] truncate cursor-pointer"
            >
              <option value="all">All Facilities ({facilities?.length || 0})</option>
              {Array.isArray(facilities) && facilities.map((f) => {
                const fid = f.facility_id ?? f.id ?? '';
                const fname = f.facility_name || f.name || 'Unnamed Facility';
                const ftype = f.facility_type ? ` (${f.facility_type.replace('_', ' ')})` : '';
                return (
                  <option key={fid} value={fid}>
                    {fname}{ftype}
                  </option>
                );
              })}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-1.5 text-slate-500 text-[10px]">
              ▼
            </div>
          </div>

          {/* 4. Time Span */}
          <div className="relative shrink-0">
            <select
              value={timeSpan}
              onChange={(e) => setTimeSpan(e.target.value)}
              className="appearance-none bg-slate-50 hover:bg-slate-100 text-slate-800 font-medium px-2.5 py-1.5 pr-6 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-teal-500 text-xs transition cursor-pointer"
            >
              <option value="4w">Last 4 Weeks</option>
              <option value="12w">Last 12 Weeks</option>
              <option value="26w">Last 26 Weeks</option>
              <option value="52w">Last 52 Weeks</option>
              <option value="all">All Time (Panel)</option>
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-1.5 text-slate-500 text-[10px]">
              ▼
            </div>
          </div>

          {/* 5. Case Status */}
          <div className="relative shrink-0">
            <select
              value={caseStatus}
              onChange={(e) => setCaseStatus(e.target.value)}
              className="appearance-none bg-slate-50 hover:bg-slate-100 text-slate-800 font-medium px-2.5 py-1.5 pr-6 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-teal-500 text-xs transition cursor-pointer"
            >
              <option value="all">All Cases</option>
              <option value="confirmed">Confirmed Only</option>
              <option value="suspected">Suspected Only</option>
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-1.5 text-slate-500 text-[10px]">
              ▼
            </div>
          </div>
        </div>

        {/* Right: Reset Action */}
        <div className="flex items-center shrink-0">
          <button
            onClick={resetFilters}
            className="flex items-center gap-1 px-2.5 py-1 text-slate-500 hover:text-slate-800 font-medium text-xs rounded hover:bg-slate-100 transition"
            title="Reset to default filters"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset</span>
          </button>
        </div>

      </div>
    </div>
  );
};
