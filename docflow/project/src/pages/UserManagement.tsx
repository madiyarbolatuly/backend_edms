
import React, { useState, useEffect } from 'react';
import { 
  UserPlus, 
  MoreHorizontal, 
  Pencil, 
  Trash2, 
  ChevronLeft, 
  ChevronRight, 
  Search 
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuTrigger 
} from '@/components/ui/dropdown-menu';

interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  additionalRoles: string[];
}

// Mock user data
const mockUsers: User[] = [
  {
    id: '1',
    name: 'Иванов Иван',
    email: 'ivan@company.com',
    role: 'Администратор',
    additionalRoles: ['Документы', 'Архив']
  },
  {
    id: '2',
    name: 'Петров Петр',
    email: 'petr@company.com',
    role: 'Пользователь',
    additionalRoles: ['Документы']
  },
  {
    id: '3',
    name: 'Сидорова Анна',
    email: 'anna@company.com',
    role: 'Модератор',
    additionalRoles: ['Архив', 'Финансы']
  },
  {
    id: '4',
    name: 'Козлов Дмитрий',
    email: 'dmitry@company.com',
    role: 'Пользователь',
    additionalRoles: []
  },
  {
    id: '5',
    name: 'Морозова Елена',
    email: 'elena@company.com',
    role: 'Администратор',
    additionalRoles: ['Документы', 'Архив', 'Финансы']
  },
  {
    id: '6',
    name: 'Волков Алексей',
    email: 'alexey@company.com',
    role: 'Модератор',
    additionalRoles: ['Документы']
  },
  {
    id: '7',
    name: 'Соколова Мария',
    email: 'maria@company.com',
    role: 'Пользователь',
    additionalRoles: ['Архив']
  },
  {
    id: '8',
    name: 'Новиков Сергей',
    email: 'sergey@company.com',
    role: 'Пользователь',
    additionalRoles: []
  },
  {
    id: '9',
    name: 'Орлова Татьяна',
    email: 'tatiana@company.com',
    role: 'Администратор',
    additionalRoles: ['Документы', 'Финансы']
  },
  {
    id: '10',
    name: 'Кузнецов Андрей',
    email: 'andrey@company.com',
    role: 'Модератор',
    additionalRoles: ['Архив']
  },
  {
    id: '11',
    name: 'Смирнова Ольга',
    email: 'olga@company.com',
    role: 'Пользователь',
    additionalRoles: ['Документы']
  },
  {
    id: '12',
    name: 'Васильев Игорь',
    email: 'igor@company.com',
    role: 'Пользователь',
    additionalRoles: ['Финансы']
  }
];

const UserManagement = () => {
  const [activeTab, setActiveTab] = useState('users');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedUsers, setSelectedUsers] = useState<string[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 5;

  // Filter users based on search query
  const filteredUsers = mockUsers.filter(user => 
    user.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
    user.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Calculate total pages
  const totalPages = Math.ceil(filteredUsers.length / itemsPerPage);

  // Get paginated users for current page
  const paginatedUsers = filteredUsers.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  // Toggle selection of a single user
  const toggleUserSelection = (userId: string) => {
    setSelectedUsers(prev => 
      prev.includes(userId)
        ? prev.filter(id => id !== userId)
        : [...prev, userId]
    );
  };

  // Toggle selection of all users on current page
  const toggleAllUsers = (checked: boolean | 'indeterminate') => {
    if (checked === 'indeterminate') return;
    
    if (checked) {
      const pageUserIds = paginatedUsers.map(user => user.id);
      setSelectedUsers(prev => {
        const existingSelected = prev.filter(id => !pageUserIds.includes(id));
        return [...existingSelected, ...pageUserIds];
      });
    } else {
      const pageUserIds = paginatedUsers.map(user => user.id);
      setSelectedUsers(prev => prev.filter(id => !pageUserIds.includes(id)));
    }
  };

  // Reset pagination when search query changes
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

  return (
    <div className="container mx-auto py-6 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center">
          <img src="/placeholder.svg?height=40&width=120&text=GO+Group" alt="GO Group Logo" className="h-10 mr-6" />

          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList>
              <TabsTrigger value="users" className="px-6">
                Пользователи
              </TabsTrigger>
              <TabsTrigger value="groups" className="px-6">
                Группы
              </TabsTrigger>
            </TabsList>

            {/* Moved TabsContent components inside Tabs component */}
            <TabsContent value="users" className="mt-0">
              <div className="flex justify-between items-center mb-4">
                <div className="relative w-80">
                  <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Поиск по имени или почте"
                    className="pl-8"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
              </div>

              <div className="border rounded-md overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">
                        <Checkbox
                          checked={paginatedUsers.length > 0 && selectedUsers.length === paginatedUsers.length}
                          onCheckedChange={toggleAllUsers}
                        />
                      </TableHead>
                      <TableHead>ФИО</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Роль</TableHead>
                      <TableHead>Группы</TableHead>
                      <TableHead className="w-12"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paginatedUsers.map((user) => (
                      <TableRow
                        key={user.id}
                        className={cn({
                          "bg-emerald-50": selectedUsers.includes(user.id),
                        })}
                      >
                        <TableCell>
                          <Checkbox
                            checked={selectedUsers.includes(user.id)}
                            onCheckedChange={() => toggleUserSelection(user.id)}
                          />
                        </TableCell>
                        <TableCell className="font-medium">{user.name}</TableCell>
                        <TableCell>{user.email}</TableCell>
                        <TableCell>{user.role}</TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {user.additionalRoles.map((role, index) => (
                              <Badge key={index} variant="outline" className="bg-gray-100">
                                {role}
                              </Badge>
                            ))}
                          </div>
                        </TableCell>
                        <TableCell>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem>
                                <Pencil className="mr-2 h-4 w-4" />
                                <span>Редактировать</span>
                              </DropdownMenuItem>
                              <DropdownMenuItem className="text-red-600">
                                <Trash2 className="mr-2 h-4 w-4" />
                                <span>Удалить</span>
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}

                    {paginatedUsers.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={6} className="text-center py-6 text-muted-foreground">
                          Пользователи не найдены
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>

              {filteredUsers.length > itemsPerPage && (
                <div className="flex justify-center mt-4">
                  <div className="flex items-center space-x-2">
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 1))}
                      disabled={currentPage === 1}
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>

                    {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                      <Button
                        key={page}
                        variant={currentPage === page ? "default" : "outline"}
                        size="icon"
                        onClick={() => setCurrentPage(page)}
                        className={cn("h-8 w-8", {
                          "bg-emerald-100 hover:bg-emerald-200 text-emerald-700": currentPage === page,
                        })}
                      >
                        {page}
                      </Button>
                    ))}

                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setCurrentPage((prev) => Math.min(prev + 1, totalPages))}
                      disabled={currentPage === totalPages}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </TabsContent>

            <TabsContent value="groups">
              <div className="flex items-center justify-center h-64 border rounded-md bg-gray-50">
                <p className="text-muted-foreground">Содержимое вкладки "Группы"</p>
              </div>
            </TabsContent>
          </Tabs>
        </div>

        <div className="flex items-center gap-2">
          <div className="text-sm mr-2">Константин К.</div>
          <Button variant="default" className="bg-emerald-100 hover:bg-emerald-200 text-emerald-700">
            <UserPlus className="mr-2 h-4 w-4" />
            <span>Добавить пользователя</span>
          </Button>
        </div>
      </div>
    </div>
  );
};

export default UserManagement;
