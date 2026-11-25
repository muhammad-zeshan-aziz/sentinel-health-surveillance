import React, { useState } from 'react';
import { 
  Activity, 
  MapPin, 
  AlertTriangle, 
  Building2, 
  FileText, 
  ShieldAlert, 
  UserCheck, 
  ChevronRight,
  RefreshCw,
  LogOut,
  X
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useFilters } from '../../context/FilterContext';

const NAV_ITEMS = [
  { id: 'overview', label: 'Overview', icon: Activity, description: 'Surveillance KPIs & Trends' },
  { id: 'hotspots', label: 'District Hotspots', icon: MapPin, description: 'Choropleth GIS & Outbreak Clusters' },
  { id: 'alerts', label: 'Early Warnings', icon: AlertTriangle, description: 'CDC EARS Anomaly Queue', badgeKey: 'activeWarnings' },
  { id: 'labs', label: 'Hospital & Labs', icon: Building2, description: 'Lab Ingestion & Facility Sync' },
  { id: 'reports', label: 'Reports & Analytics', icon: FileText, description: 'Evaluations, Backtest & Exports' },
];

export const Sidebar = ({ activeTab, setActiveTab, mobileOpen, setMobileOpen }) => {
  const { user, switchRole, demoRoles } = useAuth();
  const { activeWarningsCount } = useFilters();
  const [roleSwitcherOpen, setRoleSwitcherOpen] = useState(false);

  const handleNavClick = (tabId) => {
    setActiveTab(tabId);
    if (setMobileOpen) setMobileOpen(false);
  };

  const getRoleBadgeColor = (role) => {
    switch (role) {
      case 'district_health_officer':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
      case 'data_analyst':
        return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
      case 'hospital_staff':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
      default:
        return 'bg-slate-700 text-slate-300 border-slate-600';
    }
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div 
          className="fixed inset-0 bg-slate-950/70 z-40 lg:hidden backdrop-blur-sm"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar Container */}
      <aside 
        className={`fixed top-0 bottom-0 left-0 z-50 w-72 bg-[#0F172A] text-slate-100 flex flex-col border-r border-slate-800 transition-transform duration-300 ease-in-out ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        {/* Brand / Logo Section */}
        <div className="p-5 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-teal-500 to-emerald-600 flex items-center justify-center shadow-lg shadow-teal-500/20">
              <ShieldAlert className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-base text-white tracking-tight flex items-center gap-1.5">
                SENTINEL
                <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-teal-500/20 text-teal-300 border border-teal-500/30">
                  KP-EWS
                </span>
              </h1>
              <p className="text-xs text-slate-400 font-medium">Disease Surveillance Platform</p>
            </div>
          </div>
          {setMobileOpen && (
            <button 
              onClick={() => setMobileOpen(false)} 
              className="lg:hidden p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Region & Scope Identity Tag */}
        <div className="px-5 py-3 bg-slate-900/60 border-b border-slate-800/60 flex items-center justify-between text-[11px]">
          <span className="text-slate-400 font-medium">Jurisdiction</span>
          <span className="font-semibold text-teal-400">Khyber Pakhtunkhwa (35 D.)</span>
        </div>

        {/* Navigation List */}
        <nav className="flex-1 p-3 space-y-1.5 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            const hasBadge = item.badgeKey === 'activeWarnings' && activeWarningsCount > 0;

            return (
              <button
                key={item.id}
                onClick={() => handleNavClick(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-3 rounded-xl text-left transition-all duration-150 group ${
                  isActive
                    ? 'bg-gradient-to-r from-teal-600 to-teal-500 text-white font-semibold shadow-md shadow-teal-900/30'
                    : 'text-slate-300 hover:bg-slate-800/80 hover:text-white font-medium'
                }`}
              >
                <div className="flex items-center space-x-3 min-w-0">
                  <Icon className={`w-5 h-5 flex-shrink-0 ${isActive ? 'text-white' : 'text-slate-400 group-hover:text-teal-400'}`} />
                  <div className="truncate">
                    <div className="text-sm leading-tight">{item.label}</div>
                    <div className={`text-[11px] truncate ${isActive ? 'text-teal-100' : 'text-slate-500'}`}>
                      {item.description}
                    </div>
                  </div>
                </div>

                {hasBadge && (
                  <span className={`px-2 py-0.5 text-xs font-bold rounded-full ${
                    isActive ? 'bg-white text-teal-700' : 'bg-red-500/90 text-white animate-pulse'
                  }`}>
                    {activeWarningsCount}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* User Profile Card & Role Switcher */}
        <div className="p-3 border-t border-slate-800 bg-slate-900/70">
          <div className="p-3 rounded-xl bg-slate-800/80 border border-slate-700/60">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2.5">
                <div className="w-8 h-8 rounded-full bg-teal-500/20 border border-teal-500/40 text-teal-300 flex items-center justify-center font-bold text-xs uppercase">
                  {user?.username?.slice(0, 2) || 'DH'}
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-semibold text-white truncate">{user?.username}</div>
                  <div className="text-[10px] text-slate-400 truncate">{user?.title || user?.role}</div>
                </div>
              </div>
              <button
                onClick={() => setRoleSwitcherOpen(!roleSwitcherOpen)}
                className="p-1 text-slate-400 hover:text-teal-300 rounded hover:bg-slate-700/50 text-[11px] flex items-center gap-1 font-medium"
                title="Switch Evaluation Role"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Switch</span>
              </button>
            </div>

            <div className="flex items-center justify-between text-[10px] pt-1.5 border-t border-slate-700/50">
              <span className={`px-2 py-0.5 rounded-full border text-[9px] font-semibold uppercase tracking-wider ${getRoleBadgeColor(user?.role)}`}>
                {user?.role?.replace(/_/g, ' ')}
              </span>
              <span className="text-slate-400 truncate max-w-[120px]" title={user?.assigned_location}>
                {user?.assigned_location?.split('/')[0]}
              </span>
            </div>
          </div>

          {/* Quick Role Switcher Dropdown */}
          {roleSwitcherOpen && (
            <div className="mt-2 p-2 bg-slate-950 rounded-xl border border-slate-700 shadow-xl space-y-1">
              <div className="text-[10px] font-semibold text-slate-400 px-2 py-1 uppercase tracking-wider">
                Select Persona (CS619 RBAC)
              </div>
              {demoRoles.map((role) => (
                <button
                  key={role.username}
                  onClick={() => {
                    switchRole(role.username);
                    setRoleSwitcherOpen(false);
                  }}
                  className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs transition flex items-center justify-between ${
                    user?.username === role.username
                      ? 'bg-teal-600 text-white font-medium'
                      : 'text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  <div className="truncate">
                    <span className="font-semibold">{role.username}</span>
                    <span className="text-[10px] text-slate-400 block">{role.title}</span>
                  </div>
                  {user?.username === role.username && <UserCheck className="w-4 h-4 text-white" />}
                </button>
              ))}
            </div>
          )}
        </div>
      </aside>
    </>
  );
};
