import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { BarChart3, Boxes, Home, LogOut, Plus, Settings } from 'lucide-react'
import { useAuth } from '../core/auth'

const NAV = [
  { to: '/', label: 'Dashboard', icon: Home, end: true },
  { to: '/assets', label: 'Assets', icon: Boxes },
  { to: '/spending', label: 'Spending', icon: BarChart3 },
  { to: '/settings', label: 'Settings', icon: Settings },
]

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 64 64" className="w-8 h-8"><rect width="64" height="64" rx="14" fill="#0f766e" /><path d="M14 30 32 15l18 15v19a3 3 0 0 1-3 3H17a3 3 0 0 1-3-3z" fill="none" stroke="#fff" strokeWidth="4" strokeLinejoin="round" /><path d="m24 37 6 6 11-12" fill="none" stroke="#99f6e4" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
      <div className="leading-tight">
        <div className="font-semibold text-slate-900 text-[15px]">Home Inventory</div>
        <div className="text-[11px] text-slate-500">Assets &amp; warranties</div>
      </div>
    </div>
  )
}

export default function Layout() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  return (
    <div className="min-h-full lg:pl-64">
      {/* desktop sidebar */}
      <aside className="hidden lg:flex fixed inset-y-0 left-0 w-64 flex-col border-r border-slate-200 bg-white">
        <div className="h-16 flex items-center px-5 border-b border-slate-100"><Logo /></div>
        <div className="p-3">
          <button className="btn-primary w-full" onClick={() => nav('/assets/new')}><Plus size={18} /> Add asset</button>
        </div>
        <nav className="px-3 space-y-0.5 flex-1">
          {NAV.map(({ to, label, icon: I, end }) => (
            <NavLink key={to} to={to} end={end}
              className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 h-10 text-sm font-medium ${isActive ? 'bg-brand-50 text-brand-800' : 'text-slate-600 hover:bg-slate-50'}`}>
              <I size={18} /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-slate-100 flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-brand-100 text-brand-800 grid place-items-center text-sm font-semibold">
            {user?.display_name?.[0]?.toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium truncate">{user?.display_name}</div>
            <div className="text-[11px] text-slate-500 truncate">{user?.email}</div>
          </div>
          <button className="btn-ghost btn-sm" title="Sign out" onClick={logout}><LogOut size={16} /></button>
        </div>
      </aside>

      {/* mobile top bar */}
      <header className="lg:hidden sticky top-0 z-30 h-14 bg-white/90 backdrop-blur border-b border-slate-200 flex items-center justify-between px-4">
        <Logo />
        <button className="btn-ghost btn-sm" onClick={logout} title="Sign out"><LogOut size={18} /></button>
      </header>

      <main className="px-4 sm:px-6 lg:px-8 py-5 lg:py-8 pb-28 lg:pb-10 max-w-7xl mx-auto">
        <Outlet />
      </main>

      {/* mobile bottom nav with centre add button */}
      <nav className="lg:hidden fixed bottom-0 inset-x-0 z-30 bg-white border-t border-slate-200 pb-[env(safe-area-inset-bottom)]">
        <div className="grid grid-cols-5 h-16">
          {NAV.slice(0, 2).map(({ to, label, icon: I, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => `flex flex-col items-center justify-center gap-0.5 text-[11px] ${isActive ? 'text-brand-700 font-medium' : 'text-slate-500'}`}>
              <I size={21} /> {label}
            </NavLink>
          ))}
          <div className="grid place-items-center">
            <button onClick={() => nav('/assets/new')} className="w-12 h-12 -mt-5 rounded-2xl bg-brand-700 text-white shadow-lg shadow-brand-700/30 grid place-items-center" aria-label="Add asset">
              <Plus size={24} />
            </button>
          </div>
          {NAV.slice(2).map(({ to, label, icon: I }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `flex flex-col items-center justify-center gap-0.5 text-[11px] ${isActive ? 'text-brand-700 font-medium' : 'text-slate-500'}`}>
              <I size={21} /> {label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}
