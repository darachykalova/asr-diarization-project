import React from "react";
import { Navigate } from "react-router-dom";
import { type Role, useAuth } from "./AuthContext";

interface RoleGuardProps {
  role: Role;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function RoleGuard({ role, children, fallback }: RoleGuardProps) {
  const { user } = useAuth();
  if (!user || user.role !== role) {
    return fallback ? <>{fallback}</> : <Navigate to="/" replace />;
  }
  return <>{children}</>;
}
