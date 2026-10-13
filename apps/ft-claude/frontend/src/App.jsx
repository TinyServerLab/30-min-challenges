import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { authApi } from "./api/client.js";
import Layout from "./components/Layout.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Transactions from "./pages/Transactions.jsx";
import Categories from "./pages/Categories.jsx";
import Sources from "./pages/Sources.jsx";
import Reports from "./pages/Reports.jsx";
import Investments from "./pages/Investments.jsx";
import Subscriptions from "./pages/Subscriptions.jsx";
import SavingsPlan from "./pages/SavingsPlan.jsx";

function RequireAuth({ children }) {
  if (!authApi.isLoggedIn()) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="transactions" element={<Transactions />} />
        <Route path="categories" element={<Categories />} />
        <Route path="sources" element={<Sources />} />
        <Route path="reports" element={<Reports />} />
        <Route path="investments" element={<Investments />} />
        <Route path="subscriptions" element={<Subscriptions />} />
        <Route path="savings" element={<SavingsPlan />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
