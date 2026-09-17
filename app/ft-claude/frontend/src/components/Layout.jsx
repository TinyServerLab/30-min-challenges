import React from "react";
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

  function handleLogout() {
    authApi.logout();
    navigate("/login");
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-slate-900 text-white">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <h1 className="text-lg font-semibold">💰 Finance Tracker</h1>
          <nav className="flex gap-1 flex-wrap">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.end}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded text-sm ${
                    isActive ? "bg-slate-700 text-white" : "text-slate-300 hover:bg-slate-800"
                  }`
                }
              >
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
        </div>
      </header>
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
