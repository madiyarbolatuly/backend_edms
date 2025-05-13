
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { CheckCircle, Clock, FileClock, PlusCircle } from 'lucide-react';

interface ApprovalWorkflowProps {
  documentId?: string;
}

// Mock approval statuses
type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'awaiting';

interface Approver {
  id: string;
  name: string;
  position: string;
  avatar?: string;
  status: ApprovalStatus;
  date?: string;
  comment?: string;
}

const MOCK_APPROVERS: Approver[] = [
  {
    id: '1',
    name: 'Иван Петров',
    position: 'Главный инженер',
    avatar: '',
    status: 'approved',
    date: '2023-05-15',
    comment: 'Документ соответствует техническим требованиям.',
  },
  {
    id: '2',
    name: 'Мария Сидорова',
    position: 'Руководитель департамента',
    avatar: '',
    status: 'pending',
  },
  {
    id: '3',
    name: 'Алексей Иванов',
    position: 'Специалист по безопасности',
    avatar: '',
    status: 'awaiting',
  },
];

interface ApprovalTemplate {
  id: string;
  name: string;
  positions: string[];
}

const MOCK_TEMPLATES: ApprovalTemplate[] = [
  {
    id: '1',
    name: 'Стандартное согласование',
    positions: ['Главный инженер', 'Руководитель департамента', 'Начальник отдела'],
  },
  {
    id: '2',
    name: 'Техническое согласование',
    positions: ['Главный инженер', 'Технический специалист', 'Специалист по безопасности'],
  },
  {
    id: '3',
    name: 'Согласование с заказчиком',
    positions: ['Главный инженер', 'Представитель заказчика', 'Руководитель проекта'],
  },
];

export function ApprovalWorkflow({ documentId }: ApprovalWorkflowProps) {
  const [selectedTemplate, setSelectedTemplate] = React.useState<string>('');
  const [approvers, setApprovers] = React.useState<Approver[]>(MOCK_APPROVERS);
  const [currentTab, setCurrentTab] = React.useState<string>('current');

  const handleAddApprover = () => {
    console.log('Adding approver...');
    // Implementation would go here
  };

  const getStatusBadge = (status: ApprovalStatus) => {
    switch (status) {
      case 'approved':
        return <Badge className="bg-green-500">Одобрено</Badge>;
      case 'rejected':
        return <Badge className="bg-red-500">Отклонено</Badge>;
      case 'pending':
        return <Badge className="bg-amber-500">На рассмотрении</Badge>;
      case 'awaiting':
        return <Badge className="bg-gray-400">Ожидает очереди</Badge>;
      default:
        return null;
    }
  };

  const getApprovalProgress = () => {
    const totalApprovers = approvers.length;
    const approvedCount = approvers.filter(approver => approver.status === 'approved').length;
    
    return {
      progress: totalApprovers > 0 ? (approvedCount / totalApprovers) * 100 : 0,
      approvedCount,
      totalApprovers,
    };
  };

  const { progress, approvedCount, totalApprovers } = getApprovalProgress();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center">
          <FileClock className="h-5 w-5 mr-2" />
          Процесс согласования
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="current" onValueChange={setCurrentTab} value={currentTab}>
          <TabsList className="mb-4">
            <TabsTrigger value="current">Текущее согласование</TabsTrigger>
            <TabsTrigger value="history">История согласований</TabsTrigger>
          </TabsList>
          
          <TabsContent value="current">
            <div className="mb-4">
              <div className="flex justify-between items-center mb-2">
                <div className="text-sm font-medium">Прогресс согласования</div>
                <div className="text-sm text-muted-foreground">{approvedCount} из {totalApprovers}</div>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-green-500 h-2 rounded-full" 
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
            </div>
            
            <div className="space-y-4">
              {approvers.map((approver) => (
                <div key={approver.id} className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center space-x-3">
                    <Avatar>
                      <AvatarFallback>{approver.name.charAt(0)}</AvatarFallback>
                      {approver.avatar && <AvatarImage src={approver.avatar} />}
                    </Avatar>
                    <div>
                      <div className="font-medium">{approver.name}</div>
                      <div className="text-sm text-muted-foreground">{approver.position}</div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-3">
                    {approver.status === 'approved' && (
                      <div className="text-sm text-muted-foreground">
                        {approver.date && new Date(approver.date).toLocaleDateString()}
                      </div>
                    )}
                    {getStatusBadge(approver.status)}
                  </div>
                </div>
              ))}
            </div>
            
            <div className="mt-4 flex justify-between">
              <div className="flex-1 mr-2">
                <Select value={selectedTemplate} onValueChange={setSelectedTemplate}>
                  <SelectTrigger>
                    <SelectValue placeholder="Шаблон согласования" />
                  </SelectTrigger>
                  <SelectContent>
                    {MOCK_TEMPLATES.map((template) => (
                      <SelectItem key={template.id} value={template.id}>
                        {template.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={handleAddApprover} variant="outline">
                <PlusCircle className="h-4 w-4 mr-2" />
                Добавить согласующего
              </Button>
            </div>
          </TabsContent>
          
          <TabsContent value="history">
            <div className="flex flex-col space-y-4">
              <div className="p-4 border rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-medium">Версия 1.2</div>
                  <Badge className="bg-green-500">Одобрено</Badge>
                </div>
                <div className="text-sm text-muted-foreground mb-2">Согласовано: 15.05.2023</div>
                <div className="flex items-center">
                  <CheckCircle className="h-4 w-4 text-green-500 mr-2" />
                  <span className="text-sm">Одобрено всеми участниками процесса</span>
                </div>
              </div>
              
              <div className="p-4 border rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-medium">Версия 1.1</div>
                  <Badge className="bg-red-500">Отклонено</Badge>
                </div>
                <div className="text-sm text-muted-foreground mb-2">Рассмотрено: 05.05.2023</div>
                <div className="flex items-center">
                  <Clock className="h-4 w-4 text-amber-500 mr-2" />
                  <span className="text-sm">Требуются доработки по безопасности</span>
                </div>
              </div>
              
              <div className="p-4 border rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-medium">Версия 1.0</div>
                  <Badge className="bg-green-500">Одобрено</Badge>
                </div>
                <div className="text-sm text-muted-foreground mb-2">Согласовано: 20.04.2023</div>
                <div className="flex items-center">
                  <CheckCircle className="h-4 w-4 text-green-500 mr-2" />
                  <span className="text-sm">Одобрено с комментариями</span>
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
