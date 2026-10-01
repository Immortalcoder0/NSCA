import React from "react";
import { Route, Routes } from "react-router-dom";
import { EstateGridPage } from "./pages/EstateGridPage";
import { DeviceDetailPage } from "./pages/DeviceDetailPage";

export const EstateRoutes: React.FC = () => {
  return (
    <Routes>
      <Route index element={<EstateGridPage />} />
      <Route path=":id" element={<DeviceDetailPage />} />
    </Routes>
  );
};

export default EstateRoutes;
