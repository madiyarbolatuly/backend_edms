
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Users, UserPlus, Plus } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface User {
  id: string;
  name: string;
  email: string;
  avatar?: string;
  role: 'admin' | 'editor' | 'viewer';
  department: string;
}

// Mock users with permissions
const MOCK_USERS: User[] = [
  {
    id: 'user1',
    name: 'Алексей Петров',
    email: 'a.petrov@example.com',
    avatar: '/assets/avatars/avatar1.jpg',
    role: 'admin',
    department: 'Руководители'
  },
  {
    id: 'user2',
    name: 'Мария Иванова',
    email: 'm.ivanova@example.com',
    avatar: '/assets/avatars/avatar2.jpg',
    role: 'editor',
    department: 'Documentation Center-Документооборот'
  },
  {
    id: 'user3',
    name: 'Николай Смирнов',
    email: 'n.smirnov@example.com',
    avatar: '/assets/avatars/avatar3.jpg',
    role: 'viewer',
    department: 'Руководители'
  },
  {
    id: 'user4',
    name: 'Елена Козлова',
    email: 'e.kozlova@example.com',
    role: 'editor',
    department: 'Documentation Center-Документооборот'
  },
  {
    id: 'user5',
    name: 'Дмитрий Соколов',
    email: 'd.sokolov@example.com',
    role: 'viewer',
    department: 'Руководители'
  }
];

interface PermissionManagerProps {
  documentId?: string;
  onUpdatePermission?: (userId: string, role: 'admin' | 'editor' | 'viewer') => void;
}

export function PermissionManager({ documentId, onUpdatePermission }: PermissionManagerProps) {
  const [users, setUsers] = React.useState<User[]>(MOCK_USERS);
  
  const handleRoleChange = (userId: string, newRole: 'admin' | 'editor' | 'viewer') => {
    setUsers(users.map(user => 
      user.id === userId ? { ...user, role: newRole } : user
    ));
    
    if (onUpdatePermission) {
      onUpdatePermission(userId, newRole);
    }
  };
  
  const getRoleBadge = (role: 'admin' | 'editor' | 'viewer') => {
    switch (role) {
      case 'admin':
        return <Badge variant="outline" className="bg-red-100 text-red-800">Администратор</Badge>;
      case 'editor':
        return <Badge variant="outline" className="bg-blue-100 text-blue-800">Редактор</Badge>;
      case 'viewer':
        return <Badge variant="outline" className="bg-green-100 text-green-800">Просмотр</Badge>;
      default:
        return null;
    }
  };
  
  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(part => part[0])
      .join('')
      .toUpperCase();
  };
  
  return (
    <Card>
      <CardHeader className="flex flex-row justify-between items-center">
        <CardTitle className="flex items-center">
          <Users className="h-5 w-5 mr-2" />
          Управление доступом
        </CardTitle>
        <Button size="sm" className="gap-1">
          <UserPlus className="h-4 w-4" />
          Добавить пользователя
        </Button>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[250px]">Пользователь</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Департамент</TableHead>
              <TableHead className="w-[120px]">Права</TableHead>
              <TableHead className="w-[80px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map(user => (
              <TableRow key={user.id}>
                <TableCell className="font-medium">
                  <div className="flex items-center gap-2">
                    <Avatar className="h-8 w-8">
                      {user.avatar && <AvatarImage src={user.avatar} alt={user.name} />}
                      <AvatarFallback>{getInitials(user.name)}</AvatarFallback>
                    </Avatar>
                    <span>{user.name}</span>
                  </div>
                </TableCell>
                <TableCell className="text-muted-foreground">{user.email}</TableCell>
                <TableCell>{user.department}</TableCell>
                <TableCell>{getRoleBadge(user.role)}</TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <span className="sr-only">Открыть меню</span>
                        <svg width="15" height="15" viewBox="0 0 15 15" fill="none" xmlns="http://www.w3.org/2000/svg" className="h-4 w-4">
                          <path d="M3.625 7.5C3.625 8.12132 3.12132 8.625 2.5 8.625C1.87868 8.625 1.375 8.12132 1.375 7.5C1.375 6.87868 1.87868 6.375 2.5 6.375C3.12132 6.375 3.625 6.87868 3.625 7.5ZM8.625 7.5C8.625 8.12132 8.12132 8.625 7.5 8.625C6.87868 8.625 6.375 8.12132 6.375 7.5C6.375 6.87868 6.87868 6.375 7.5 6.375C8.12132 6.375 8.625 6.87868 8.625 7.5ZM13.625 7.5C13.625 8.12132 13.1213 8.625 12.5 8.625C11.8787 8.625 11.375 8.12132 11.375 7.5C11.375 6.87868 11.8787 6.375 12.5 6.375C13.1213 6.375 13.625 6.87868 13.625 7.5Z" fill="currentColor" fillRule="evenodd" clipRule="evenodd"></path>
                        </svg>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => handleRoleChange(user.id, 'admin')}>
                        Администратор
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleRoleChange(user.id, 'editor')}>
                        Редактор
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleRoleChange(user.id, 'viewer')}>
                        Просмотр
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem className="text-destructive">
                        Удалить доступ
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
