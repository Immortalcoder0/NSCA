import React from "react";
import { Route, Routes } from "react-router-dom";
import { RemediationPlaybookPage } from "./pages/RemediationPlaybookPage";
import { RemediationDryRunPage } from "./pages/RemediationDryRunPage";

export const RemediationRoutes: React.FC = () => {
  return (
    <Routes>
      <Route index element={<RemediationPlaybookPage />} />
      <Route path="dry-run" element={<RemediationDryRunPage />} />
    </Routes>
  );
};

export default RemediationRoutes;
