
import { useQuery, useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useToast } from '@/hooks/use-toast';
import { User, LoginResponse } from '@/types/auth';

const API_URL = 'http://localhost:8000'; // Replace with your FastAPI backend URL

export const useAuth = () => {
  const { toast } = useToast();
  const navigate = useNavigate();

  const { data: user, isLoading: isLoadingUser } = useQuery({
    queryKey: ['user'],
    queryFn: async (): Promise<User | null> => {
      const token = localStorage.getItem('token');
      if (!token) return null;

      const response = await fetch(`${API_URL}/users/me`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        localStorage.removeItem('token');
        return null;
      }

      return response.json();
    }
  });

  const loginMutation = useMutation({
    mutationFn: async ({ email, password }: { email: string; password: string }): Promise<LoginResponse> => {
      const response = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        throw new Error('Login failed');
      }

      return response.json();
    },
    onSuccess: (data) => {
      localStorage.setItem('token', data.access_token);
      toast({
        title: "Success",
        description: "Successfully logged in",
      });
      navigate('/');
    },
    onError: () => {
      toast({
        title: "Error",
        description: "Invalid credentials",
        variant: "destructive",
      });
    },
  });

  const logout = () => {
    localStorage.removeItem('token');
    navigate('/login');
  };

  return {
    user,
    isLoadingUser,
    login: loginMutation.mutate,
    isLoggingIn: loginMutation.isPending,
    logout,
    isAuthenticated: !!user,
  };
};
