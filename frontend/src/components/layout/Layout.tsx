/**
 * Layout - Contenedor principal con sidebar y footer - SQA Branding
 */
import { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Footer from './Footer';

const SIDEBAR_KEY = 'sidebar_collapsed';

export default function Layout() {
  const [collapsed, setCollapsed] = useState(() => {
    const saved = localStorage.getItem(SIDEBAR_KEY);
    return saved === 'true';
  });

  useEffect(() => {
    localStorage.setItem(SIDEBAR_KEY, String(collapsed));
  }, [collapsed]);

  const toggleSidebar = () => setCollapsed((prev) => !prev);

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col">
      <Sidebar collapsed={collapsed} onToggle={toggleSidebar} />

      <main
        className={`transition-all duration-300 flex-1 overflow-x-hidden overflow-y-auto ${
          collapsed ? 'ml-16' : 'ml-72'
        }`}
      >
        <div className="w-full px-6 py-6">
          <Outlet />
        </div>
      </main>

      <div
        className={`transition-all duration-300 ${
          collapsed ? 'ml-16' : 'ml-72'
        }`}
      >
        <Footer />
      </div>
    </div>
  );
}
