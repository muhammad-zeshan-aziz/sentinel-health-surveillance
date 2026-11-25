import React, { useState, useEffect, useRef } from 'react';
import L from 'leaflet';
import { 
  Layers, 
  MapPin, 
  AlertTriangle, 
  TrendingUp, 
  Info, 
  X, 
  Building2, 
  Sparkles,
  Maximize2
} from 'lucide-react';
import { useFilters } from '../context/FilterContext';

// Color Scales for Choropleth
const GET_OBSERVED_COLOR = (tier, incidence) => {
  if (tier === 'data_incomplete') return '#94A3B8'; // Slate 400 for missing
  if (tier === 'hotspot' || incidence >= 50) return '#DC2626'; // Red 600
  if (tier === 'moderate' || incidence >= 15) return '#F59E0B'; // Amber 500
  return '#10B981'; // Emerald 500
};

const GET_FORECAST_COLOR = (tier, forecastIncidence) => {
  if (tier === 'data_incomplete') return '#94A3B8';
  if (tier === 'hotspot' || forecastIncidence >= 50) return '#7C3AED'; // Violet 600 for Forecast Hotspot
  if (tier === 'moderate' || forecastIncidence >= 15) return '#D97706'; // Amber 600
  return '#0D9488'; // Teal 600
};

export const HotspotsView = () => {
  const { disease, caseStatus, refreshTrigger } = useFilters();
  
  // Controls
  const [activeLayer, setActiveLayer] = useState('observed'); // 'observed' | 'forecast'
  const [metricMode, setMetricMode] = useState('incidence'); // 'incidence' | 'counts'
  
  // Data
  const [geoJsonData, setGeoJsonData] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // Drilldown panel on click
  const [selectedDistrict, setSelectedDistrict] = useState(null);
  const [drilldownData, setDrilldownData] = useState(null);
  const [drilldownLoading, setDrilldownLoading] = useState(false);

  // Map references
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const geoJsonLayerRef = useRef(null);

  // 1. Fetch GeoJSON
  useEffect(() => {
    setLoading(true);
    fetch(`/api/hotspots/map?disease=${disease}&case_status=${caseStatus || 'all'}`)
      .then(res => res.json())
      .then(data => {
        setGeoJsonData(data);
      })
      .catch(err => console.error('Failed to load hotspot map:', err))
      .finally(() => setLoading(false));
  }, [disease, caseStatus, refreshTrigger]);

  // 2. Fetch District Drilldown when selected
  useEffect(() => {
    if (!selectedDistrict) {
      setDrilldownData(null);
      return;
    }
    setDrilldownLoading(true);
    fetch(`/api/hotspots/drilldown/${selectedDistrict.district_pcode}?disease=${disease}`)
      .then(res => res.json())
      .then(data => setDrilldownData(data))
      .catch(err => console.error('Failed to load district drilldown:', err))
      .finally(() => setDrilldownLoading(false));
  }, [selectedDistrict, disease]);

  // 3. Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      // Center of Khyber Pakhtunkhwa: Lat 34.0, Lon 71.5
      const map = L.map(mapContainerRef.current, {
        center: [34.4, 71.8],
        zoom: 7,
        zoomControl: true,
        attributionControl: false
      });

      L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 16,
        attribution: '&copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
      }).addTo(map);

      mapInstanceRef.current = map;
    }

    return () => {
      // Cleanup on unmount
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // 4. Update GeoJSON Layer when data, layer mode, or metric changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !geoJsonData) return;

    // Remove existing GeoJSON layer if any
    if (geoJsonLayerRef.current) {
      map.removeLayer(geoJsonLayerRef.current);
    }

    const onEachFeature = (feature, layer) => {
      const p = feature.properties || {};
      const isForecast = activeLayer === 'forecast';

      // Tooltip HTML content
      const casesVal = isForecast ? p.forecast_t1?.predicted_mean : p.cases;
      const incVal = isForecast ? p.forecast_t1?.forecast_incidence_per_100k : p.incidence_per_100k;
      const tierVal = isForecast ? p.forecast_t1?.forecast_hotspot_tier : p.hotspot_tier;

      const tooltipContent = `
        <div style="font-family: inherit; min-width: 170px;">
          <div style="font-weight: 700; font-size: 13px; color: #0D9488; border-bottom: 1px solid #334155; padding-bottom: 3px; margin-bottom: 4px;">
            ${p.district_name || 'District'} (${p.district_pcode})
          </div>
          <div style="font-size: 11px; color: #cbd5e1; line-height: 1.4;">
            <div>Division: <b>${p.division || 'KP'}</b></div>
            <div>Population: <b>${(p.population_2023 || 0).toLocaleString()}</b></div>
            <div style="margin-top: 4px; padding-top: 4px; border-top: 1px solid #334155;">
              <span>${isForecast ? 'Forecast (t+1)' : 'Observed Cases'}: <b>${casesVal !== null ? casesVal : 'NR (Missing)'}</b></span>
            </div>
            <div>
              <span>Incidence: <b>${incVal !== null ? incVal + ' / 100k' : 'N/A'}</b></span>
            </div>
            <div style="margin-top: 3px;">
              <span>Status: <b style="text-transform: capitalize; color: ${tierVal === 'hotspot' ? '#f87171' : '#34d399'}">${tierVal || 'routine'}</b></span>
            </div>
          </div>
        </div>
      `;

      layer.bindTooltip(tooltipContent, {
        className: 'custom-map-tooltip',
        direction: 'auto',
        sticky: true
      });

      // Hover and Click events
      layer.on({
        mouseover: (e) => {
          const l = e.target;
          l.setStyle({
            weight: 3,
            color: '#0F172A',
            fillOpacity: 0.85
          });
          l.bringToFront();
        },
        mouseout: (e) => {
          if (geoJsonLayerRef.current) {
            geoJsonLayerRef.current.resetStyle(e.target);
          }
        },
        click: () => {
          setSelectedDistrict(p);
        }
      });
    };

    const styleFeature = (feature) => {
      const p = feature.properties || {};
      const isForecast = activeLayer === 'forecast';

      const tier = isForecast ? p.forecast_t1?.forecast_hotspot_tier : p.hotspot_tier;
      const inc = isForecast ? (p.forecast_t1?.forecast_incidence_per_100k || 0) : (p.incidence_per_100k || 0);

      const fillColor = isForecast
        ? GET_FORECAST_COLOR(tier, inc)
        : GET_OBSERVED_COLOR(tier, inc);

      return {
        fillColor: fillColor,
        weight: 1.5,
        opacity: 1,
        color: '#FFFFFF',
        fillOpacity: tier === 'data_incomplete' ? 0.35 : 0.7
      };
    };

    const geoLayer = L.geoJSON(geoJsonData, {
      style: styleFeature,
      onEachFeature: onEachFeature
    }).addTo(map);

    geoJsonLayerRef.current = geoLayer;

    // Fit map bounds to KP features
    try {
      map.fitBounds(geoLayer.getBounds(), { padding: [20, 20] });
    } catch (e) {
      console.warn('Could not fit bounds:', e);
    }

  }, [geoJsonData, activeLayer, metricMode]);

  const resetView = () => {
    if (mapInstanceRef.current && geoJsonLayerRef.current) {
      mapInstanceRef.current.fitBounds(geoJsonLayerRef.current.getBounds(), { padding: [20, 20] });
    }
  };

  return (
    <div className="space-y-4 relative">
      
      {/* Top Controls Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        
        {/* Layer Mode Switcher: Observed vs Forecast */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Layer:
          </span>
          <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1 text-xs">
            <button
              onClick={() => setActiveLayer('observed')}
              className={`px-3 py-1.5 rounded-md font-semibold transition ${
                activeLayer === 'observed'
                  ? 'bg-teal-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Observed Hotspots (Current)
            </button>
            <button
              onClick={() => setActiveLayer('forecast')}
              className={`px-3 py-1.5 rounded-md font-semibold transition flex items-center gap-1.5 ${
                activeLayer === 'forecast'
                  ? 'bg-purple-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              Forecast Hotspots (t+1 Outlook)
            </button>
          </div>
        </div>

        {/* Metric Mode: Incidence vs Counts */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Metric:
          </span>
          <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1 text-xs">
            <button
              onClick={() => setMetricMode('incidence')}
              className={`px-3 py-1.5 rounded-md font-semibold transition ${
                metricMode === 'incidence'
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Incidence per 100k
            </button>
            <button
              onClick={() => setMetricMode('counts')}
              className={`px-3 py-1.5 rounded-md font-semibold transition ${
                metricMode === 'counts'
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Raw Counts
            </button>
          </div>

          <button
            onClick={resetView}
            className="p-1.5 text-slate-500 hover:text-slate-800 bg-slate-100 rounded-lg border border-slate-200 transition"
            title="Reset Map Zoom & Bounds"
          >
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>

      </div>

      {/* Map Canvas + Side Panel Layout */}
      <div className="relative bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden h-[620px]">
        
        {/* Leaflet Map Div */}
        <div ref={mapContainerRef} className="w-full h-full" />

        {/* Floating Legend Box on Map */}
        <div className="absolute bottom-4 left-4 z-20 bg-white/95 backdrop-blur-md p-3 rounded-xl border border-slate-200 shadow-md text-xs max-w-xs">
          <div className="font-bold text-slate-800 mb-2 flex items-center justify-between">
            <span>{activeLayer === 'forecast' ? 'Forecast Hotspot Scale (t+1)' : 'Observed Hotspot Scale'}</span>
          </div>

          <div className="space-y-1.5 text-[11px]">
            <div className="flex items-center gap-2">
              <span className={`w-3.5 h-3.5 rounded ${activeLayer === 'forecast' ? 'bg-purple-600' : 'bg-red-600'}`}></span>
              <span className="font-medium text-slate-700">Hotspot / Surge (Incidence ≥ 50)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className={`w-3.5 h-3.5 rounded ${activeLayer === 'forecast' ? 'bg-amber-600' : 'bg-amber-500'}`}></span>
              <span className="font-medium text-slate-700">Moderate Alert (15 ≤ Inc &lt; 50)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className={`w-3.5 h-3.5 rounded ${activeLayer === 'forecast' ? 'bg-teal-600' : 'bg-emerald-500'}`}></span>
              <span className="font-medium text-slate-700">Low / Baseline (Inc &lt; 15)</span>
            </div>
            <div className="flex items-center gap-2 pt-1 border-t border-slate-200">
              <span className="w-3.5 h-3.5 rounded bg-slate-400 opacity-60"></span>
              <span className="font-medium text-slate-600">Missing / Incomplete Data (NR)</span>
            </div>
          </div>
          <p className="text-[10px] text-slate-400 mt-2">
            Click any district to inspect 12-week trends and local sentinel facilities.
          </p>
        </div>

        {/* District Detail Drawer / Panel (Slides from Right) */}
        {selectedDistrict && (
          <div className="absolute top-0 right-0 bottom-0 w-96 bg-white/98 backdrop-blur-md border-l border-slate-200 shadow-2xl z-20 p-5 flex flex-col overflow-y-auto">
            <div className="flex items-start justify-between pb-3 border-b border-slate-200">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-teal-600 block">
                  District Profile
                </span>
                <h3 className="text-base font-bold text-slate-900">
                  {selectedDistrict.district_name}
                </h3>
                <span className="text-xs text-slate-500 font-mono">
                  {selectedDistrict.district_pcode} • {selectedDistrict.division} Division
                </span>
              </div>
              <button
                onClick={() => setSelectedDistrict(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="mt-4 space-y-4 flex-1">
              {/* Population & Latest Metric */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                  <span className="text-slate-500 block">2023 Census Pop</span>
                  <span className="text-sm font-bold text-slate-800">
                    {(selectedDistrict.population_2023 || 0).toLocaleString()}
                  </span>
                </div>
                <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                  <span className="text-slate-500 block">Current Incidence</span>
                  <span className="text-sm font-bold text-slate-800">
                    {selectedDistrict.incidence_per_100k || 0} / 100k
                  </span>
                </div>
              </div>

              {/* Forecast (t+1) Card */}
              {selectedDistrict.forecast_t1 && (
                <div className="p-3 bg-purple-50 border border-purple-200 rounded-xl text-xs space-y-1.5">
                  <div className="flex items-center justify-between text-purple-900 font-bold">
                    <span className="flex items-center gap-1">
                      <Sparkles className="w-4 h-4 text-purple-600" />
                      7-Day Forecast (t+1)
                    </span>
                    <span className="px-2 py-0.5 rounded-full bg-purple-200 text-purple-800 text-[10px] uppercase">
                      {selectedDistrict.forecast_t1.outbreak_risk}
                    </span>
                  </div>
                  <div className="flex justify-between text-slate-700 pt-1">
                    <span>Projected Cases:</span>
                    <span className="font-bold text-slate-900">
                      {selectedDistrict.forecast_t1.predicted_mean}
                    </span>
                  </div>
                  <div className="flex justify-between text-slate-600 text-[11px]">
                    <span>95% Conformal CI:</span>
                    <span>
                      [{selectedDistrict.forecast_t1.ci_lower_95} – {selectedDistrict.forecast_t1.ci_upper_95}]
                    </span>
                  </div>
                </div>
              )}

              {/* Local Sentinel Facilities */}
              <div>
                <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Building2 className="w-4 h-4 text-teal-600" />
                  Designated Sentinel Hospitals
                </h4>

                {drilldownLoading ? (
                  <div className="text-xs text-slate-400 py-4 text-center">
                    Loading facility list...
                  </div>
                ) : drilldownData?.facilities?.length ? (
                  <div className="space-y-1.5 max-h-48 overflow-y-auto">
                    {drilldownData.facilities.map((fac) => (
                      <div key={fac.id} className="p-2 rounded bg-slate-50 border border-slate-200 text-xs flex justify-between items-center">
                        <div>
                          <div className="font-semibold text-slate-800 truncate max-w-[190px]">
                            {fac.name}
                          </div>
                          <div className="text-[10px] text-slate-500">
                            {fac.facility_type} • {fac.tehsil || 'Tehsil'}
                          </div>
                        </div>
                        {fac.is_spotlight && (
                          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-teal-100 text-teal-800 border border-teal-200">
                            Spotlight
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-xs text-slate-400 py-3 text-center">
                    No designated facilities registered in this district.
                  </div>
                )}
              </div>

              {/* Recent 12-Week Cases Trend */}
              {drilldownData?.recent_trend?.length > 0 && (
                <div>
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    <TrendingUp className="w-4 h-4 text-indigo-600" />
                    Recent Weekly History
                  </h4>
                  <div className="border border-slate-200 rounded-lg overflow-hidden text-xs">
                    <div className="grid grid-cols-3 bg-slate-100 p-1.5 font-semibold text-slate-600 text-[11px]">
                      <span>Epi Week</span>
                      <span className="text-center">Total Cases</span>
                      <span className="text-right">Incidence</span>
                    </div>
                    <div className="divide-y divide-slate-100 max-h-40 overflow-y-auto">
                      {drilldownData.recent_trend.map((pt, idx) => (
                        <div key={idx} className="grid grid-cols-3 p-1.5 text-[11px] hover:bg-slate-50">
                          <span className="font-medium text-slate-700">{pt.year}-W{pt.epi_week}</span>
                          <span className="text-center text-slate-900 font-bold">{pt.total_cases ?? 'NR'}</span>
                          <span className="text-right text-slate-600">{pt.incidence_per_100k ?? 'N/A'}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

            </div>
          </div>
        )}

      </div>
    </div>
  );
};
