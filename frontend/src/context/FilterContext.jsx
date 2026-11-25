import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const FilterContext = createContext();

export const FilterProvider = ({ children }) => {
  // Global synchronized filter criteria
  const [disease, setDisease] = useState('Malaria');
  const [districtPcode, setDistrictPcode] = useState('all');
  const [facilityId, setFacilityId] = useState('all');
  const [timeSpan, setTimeSpan] = useState('12w');
  const [caseStatus, setCaseStatus] = useState('all');
  const [metricMode, setMetricMode] = useState('incidence'); // 'incidence' | 'counts'

  // Reference metadata lists
  const [districts, setDistricts] = useState([]);
  const [facilities, setFacilities] = useState([]);
  const [activeWarningsCount, setActiveWarningsCount] = useState(0);
  const [lastRefreshed, setLastRefreshed] = useState(new Date().toLocaleTimeString());
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [isSyntheticActive, setIsSyntheticActive] = useState(true);

  // Load districts and facilities once
  useEffect(() => {
    fetch('/api/surveillance/districts')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          // Normalize properties and sort alphabetically by district name
          const normalized = data.map(d => ({
            ...d,
            pcode: d.pcode || d.district_pcode || '',
            district_pcode: d.district_pcode || d.pcode || '',
            name: d.name || d.district_name || 'Unknown District',
            district_name: d.district_name || d.name || 'Unknown District'
          })).sort((a, b) => (a.district_name || a.name || '').localeCompare(b.district_name || b.name || ''));
          setDistricts(normalized);
        }
      })
      .catch(err => console.error('Failed to load districts:', err));

    fetch('/api/surveillance/facilities')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          // Normalize properties and sort alphabetically by facility name
          const normalized = data.map(f => ({
            ...f,
            id: f.id ?? f.facility_id ?? 0,
            facility_id: f.facility_id ?? f.id ?? 0,
            name: f.name || f.facility_name || 'Unknown Facility',
            facility_name: f.facility_name || f.name || 'Unknown Facility'
          })).sort((a, b) => (a.facility_name || a.name || '').localeCompare(b.facility_name || b.name || ''));
          setFacilities(normalized);
        }
      })
      .catch(err => console.error('Failed to load facilities:', err));
  }, []);

  // Update active warnings count whenever disease changes or refresh is triggered
  useEffect(() => {
    fetch(`/api/alerts/queue?disease=${disease}&acknowledged=false`)
      .then(res => res.json())
      .then(data => {
        if (data && data.total_active_warnings !== undefined) {
          setActiveWarningsCount(data.total_active_warnings);
        } else if (Array.isArray(data?.alerts)) {
          setActiveWarningsCount(data.alerts.length);
        }
      })
      .catch(err => console.error('Failed to load alert count:', err));
  }, [disease, refreshTrigger]);

  const refreshData = useCallback(() => {
    setLastRefreshed(new Date().toLocaleTimeString());
    setRefreshTrigger(prev => prev + 1);
  }, []);

  const resetFilters = useCallback(() => {
    setDisease('Malaria');
    setDistrictPcode('all');
    setFacilityId('all');
    setTimeSpan('12w');
    setCaseStatus('all');
    setMetricMode('incidence');
    refreshData();
  }, [refreshData]);

  // Derived filtered facilities based on selected district
  const filteredFacilities = districtPcode === 'all'
    ? facilities
    : facilities.filter(f => f.district_pcode === districtPcode);

  return (
    <FilterContext.Provider
      value={{
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
        metricMode,
        setMetricMode,
        districts,
        facilities: filteredFacilities,
        allFacilities: facilities,
        activeWarningsCount,
        lastRefreshed,
        refreshTrigger,
        refreshData,
        resetFilters,
        isSyntheticActive,
        setIsSyntheticActive
      }}
    >
      {children}
    </FilterContext.Provider>
  );
};

export const useFilters = () => useContext(FilterContext);
