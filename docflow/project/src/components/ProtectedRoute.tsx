import { Navigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredPermissions?: string[];
}

export const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  // Temporarily return children directly to make routes open
  return <>{children}</>;
};