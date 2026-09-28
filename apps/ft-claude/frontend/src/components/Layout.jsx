import React, { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { authApi } from "../api/client.js";

const links = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/transactions", label: "Transactions" },
  { to: "/categories", label: "Categories" },
  { to: "/sources", label: "Payment Sources" },
  { to: "/investments", label: "Investments" },
  { to: "/reports", label: "Reports" },
];

export default function Layout() {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  function handleLogout() {
    authApi.logout();
    navigate("/login");
  }

  function navLinkClass({ isActive }) {
    return `block px-3 py-2 rounded text-sm ${
      isActive ? "bg-slate-700 text-white" : "text-slate-300 hover:bg-slate-800"
    }`;
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-slate-900 text-white sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <h1 className="text-lg font-semibold">💰 Finance Tracker</h1>

          {/* Desktop nav */}
          <nav className="hidden md:flex gap-1 flex-wrap">
            {links.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end} className={navLinkClass}>
                {l.label}
              </NavLink>
            ))}
            <button
              onClick={handleLogout}
              className="px-3 py-1.5 rounded text-sm text-slate-300 hover:bg-slate-800"
            >
              Log out
            </button>
          </nav>

          {/* Mobile hamburger button */}
          <button
            onClick={() => setMenuOpen((v) => !v)}
            aria-label="Toggle menu"
            aria-expanded={menuOpen}
            className="md:hidden inline-flex items-center justify-center w-9 h-9 rounded hover:bg-slate-800"
          >
            {menuOpen ? (
              <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>

        {/* Mobile dropdown nav */}
        {menuOpen && (
          <nav className="md:hidden border-t border-slate-800 px-4 py-2 space-y-1">
            {links.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end} className={navLinkClass} onClick={() => setMenuOpen(false)}>
                {l.label}
              </NavLink>
            ))}
            <button
              onClick={() => {
                setMenuOpen(false);
                handleLogout();
              }}
              className="block w-full text-left px-3 py-2 rounded text-sm text-slate-300 hover:bg-slate-800"
            >
              Log out
            </button>
          </nav>
        )}
      </header>
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
