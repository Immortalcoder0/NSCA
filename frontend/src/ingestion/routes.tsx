import React from "react";
import { Route, Routes } from "react-router-dom";
import { IngestionDashboardPage } from "./pages/IngestionDashboardPage";

export const IngestionRoutes: React.FC = () => {
  return (
    <Routes>
      <Route index element={<IngestionDashboardPage />} />
      <Route path=":id" element={<IngestionDashboardPage />} />
    </Routes>
  );
};

export default IngestionRoutes;
