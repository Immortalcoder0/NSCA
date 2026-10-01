import React from "react";
import { Route, Routes } from "react-router-dom";
import { AttackPathExplorerPage } from "./pages/AttackPathExplorerPage";

export const AttackPathRoutes: React.FC = () => {
  return (
    <Routes>
      <Route index element={<AttackPathExplorerPage />} />
    </Routes>
  );
};

export default AttackPathRoutes;
