import React, { useState } from 'react';
import { AuthProvider } from './context/AuthContext';
import { FilterProvider } from './context/FilterContext';
import { Sidebar } from './components/layout/Sidebar';
import { TopHeader } from './components/layout/TopHeader';
import { FilterBar } from './components/layout/FilterBar';

// Views
import { OverviewView } from './views/OverviewView';
import { HotspotsView } from './views/HotspotsView';
import { EarlyWarningsView } from './views/EarlyWarningsView';
import { HospitalsLabsView } from './views/HospitalsLabsView';
import { ReportsView } from './views/ReportsView';

function AppContent() {
  const [activeTab, setActiveTab] = useState('overview');
  const [mobileOpen, setMobileOpen] = useState(false);

  const renderActiveView = () => {
    switch (activeTab) {
      case 'overview':
        return <OverviewView />;
      case 'hotspots':
        return <HotspotsView />;
      case 'alerts':
        return <EarlyWarningsView />;
      case 'labs':
        return <HospitalsLabsView />;
      case 'reports':
        return <ReportsView />;
      default:
        return <OverviewView />;
    }
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex text-slate-800">
      
      {/* Sidebar */}
      <Sidebar 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        mobileOpen={mobileOpen} 
        setMobileOpen={setMobileOpen} 
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 lg:pl-72">
        {/* Top Header */}
        <TopHeader 
          activeTab={activeTab} 
          setActiveTab={setActiveTab} 
          setMobileOpen={setMobileOpen} 
        />

        {/* Global Persistent Filter Subheader */}
        <FilterBar />

        {/* Active View Container */}
        <main className="flex-1 p-4 sm:p-6 max-w-7xl w-full mx-auto">
          {renderActiveView()}
        </main>
      </div>

    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <FilterProvider>
        <AppContent />
      </FilterProvider>
    </AuthProvider>
  );
}
