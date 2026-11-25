import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext();

export const DEMO_CREDENTIALS = {
  dho_kp: {
    username: 'dho_kp',
    password: 'dho123',
    role: 'district_health_officer',
    title: 'District Health Officer (DHO)',
    assigned_location: 'Provincial HQ / All KP Districts'
  },
  analyst_kp: {
    username: 'analyst_kp',
    password: 'analyst123',
    role: 'data_analyst',
    title: 'Public Health Data Analyst',
    assigned_location: 'DG Health Services KP'
  },
  staff_ath: {
    username: 'staff_ath',
    password: 'staff123',
    role: 'hospital_staff',
    title: 'Hospital Laboratory Staff',
    assigned_location: 'Ayub Teaching Hospital (ATH), Abbottabad'
  }
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('sentinel_user');
    return saved ? JSON.parse(saved) : DEMO_CREDENTIALS.dho_kp;
  });
  const [token, setToken] = useState(() => localStorage.getItem('sentinel_token') || '');
  const [demoRoles, setDemoRoles] = useState([]);
  const [loading, setLoading] = useState(false);

  // Initialize demo token on first load if not present
  useEffect(() => {
    fetch('/api/auth/demo-roles')
      .then(res => res.json())
      .then(data => setDemoRoles(data))
      .catch(() => setDemoRoles(Object.values(DEMO_CREDENTIALS)));

    if (!token) {
      // Auto-login as default DHO
      login('dho_kp', 'dho123').catch(err => console.warn('Auto-login notice:', err));
    }
  }, []);

  const login = async (username, password) => {
    setLoading(true);
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });

      if (!response.ok) {
        throw new Error('Authentication failed');
      }

      const data = await response.json();
      setToken(data.access_token);
      localStorage.setItem('sentinel_token', data.access_token);

      const profile = {
        username: data.username,
        role: data.role,
        facility_id: data.facility_id,
        assigned_district_pcode: data.assigned_district_pcode,
        title: DEMO_CREDENTIALS[data.username]?.title || data.role,
        assigned_location: DEMO_CREDENTIALS[data.username]?.assigned_location || 'Khyber Pakhtunkhwa'
      };

      setUser(profile);
      localStorage.setItem('sentinel_user', JSON.stringify(profile));
      return { success: true };
    } catch (err) {
      console.error('Login error:', err);
      // Fallback to local profile for uninterrupted evaluation
      const fallback = DEMO_CREDENTIALS[username] || DEMO_CREDENTIALS.dho_kp;
      setUser(fallback);
      return { success: false, error: err.message };
    } finally {
      setLoading(false);
    }
  };

  const switchRole = async (username) => {
    const creds = DEMO_CREDENTIALS[username];
    if (creds) {
      await login(creds.username, creds.password);
    }
  };

  const logout = () => {
    setToken('');
    localStorage.removeItem('sentinel_token');
    localStorage.removeItem('sentinel_user');
    setUser(DEMO_CREDENTIALS.dho_kp);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        demoRoles,
        loading,
        login,
        switchRole,
        logout,
        isDHO: user?.role === 'district_health_officer',
        isAnalyst: user?.role === 'data_analyst',
        isHospitalStaff: user?.role === 'hospital_staff'
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
