import React from "react";
import { Route, Routes } from "react-router-dom";
import { AdminDashboardPage } from "./pages/AdminDashboardPage";
import { UsersManagementPage } from "./pages/UsersManagementPage";
import { CredentialVaultPage } from "./pages/CredentialVaultPage";
import { AuditLogViewerPage } from "./pages/AuditLogViewerPage";

export const AdminRoutes: React.FC = () => {
  return (
    <Routes>
      <Route index element={<AdminDashboardPage />} />
      <Route path="users" element={<UsersManagementPage />} />
      <Route path="credentials" element={<CredentialVaultPage />} />
      <Route path="audit-log" element={<AuditLogViewerPage />} />
    </Routes>
  );
};

export default AdminRoutes;
