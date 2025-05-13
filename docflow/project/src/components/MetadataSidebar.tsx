
import React, { useState } from 'react';
import { Document } from '@/types/document';
import { MetadataCard } from './MetadataCard';
import {
  FileText, File, FileSpreadsheet, FileImage, 
  Folder, X, Download, Share2, Star, Trash,
  Edit, Clock, User, Eye
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { format } from 'date-fns';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';

// Import components needed for the detailed view
import { ActivityItem } from '@/components/ActivityItem';
import { CustomFieldsPanel } from '@/components/metadata/CustomFieldsPanel';
import { PermissionManager } from '@/components/permissions/PermissionManager';
import { VersionHistoryList } from '@/components/VersionHistoryList';
import { useToast } from '@/hooks/use-toast';

// Define the proper activity type
type ActivityAction = "viewed" | "modified" | "commented" | "uploaded" | "deleted" | "restored" | "downloaded" | "shared";

interface Activity {
  id: string;
  action: ActivityAction;
  timestamp: string;
  user: string;
  date: string;
}

interface MetadataSidebarProps {
  document?: Document;
  onClose: () => void;
}

export function MetadataSidebar({ document, onClose }: MetadataSidebarProps) {
  const [activeTab, setActiveTab] = useState('details');
  const { toast } = useToast();

  if (!document) {
    return (
      <div className="h-full flex items-center justify-center border-l p-6">
        <p className="text-muted-foreground text-center">
          Выберите файл или папку для просмотра деталей
        </p>
      </div>
    );
  }

  const renderIcon = () => {
    switch (document.type) {
      case 'pdf':
        return <FileText className="h-16 w-16 text-red-500" />;
      case 'doc':
        return <FileText className="h-16 w-16 text-blue-500" />;
      case 'xlsx':
        return <FileSpreadsheet className="h-16 w-16 text-green-500" />;
      case 'image':
        return <FileImage className="h-16 w-16 text-purple-500" />;
      case 'folder':
        return <Folder className="h-16 w-16 text-yellow-500" />;
      default:
        return <File className="h-16 w-16 text-gray-500" />;
    }
  };

  const isFolder = document.type === 'folder';
  const fileExtension = document.name.split('.').pop()?.toUpperCase() || '';
  const modifiedDate = new Date(document.modified);

  // Mock data for activities with correct type
  const activities: Activity[] = [
    {
      id: '1',
      action: "viewed",
      timestamp: new Date(Date.now() - 3600000).toISOString(),
      user: 'Александр Иванов',
      date: new Date(Date.now() - 3600000).toISOString()
    },
    {
      id: '2',
      action: "modified",
      timestamp: new Date(Date.now() - 86400000).toISOString(),
      user: 'Мария Петрова',
      date: new Date(Date.now() - 86400000).toISOString()
    },
    {
      id: '3',
      action: "commented",
      timestamp: new Date(Date.now() - 172800000).toISOString(),
      user: 'Дмитрий Соколов',
      date: new Date(Date.now() - 172800000).toISOString()
    },
    {
      id: '4',
      action: "uploaded",
      timestamp: new Date(Date.now() - 259200000).toISOString(),
      user: 'Елена Смирнова',
      date: new Date(Date.now() - 259200000).toISOString()
    }
  ];

  // Mock versions
  const versions = [
    { 
      id: '1', 
      version: '1.0', 
      modified: '2023-01-01', 
      modifiedBy: 'Иван Петров',
      size: '1.2 MB',
      comment: 'Первоначальная версия',
      versionNumber: 1,
      createdAt: '2023-01-01',
      createdBy: 'Иван Петров',
      comments: 'Первоначальная версия'
    },
    { 
      id: '2', 
      version: '1.1', 
      modified: '2023-02-15', 
      modifiedBy: 'Мария Иванова',
      size: '1.3 MB',
      versionNumber: 2,
      createdAt: '2023-02-15',
      createdBy: 'Мария Иванова',
      comments: ''
    },
    { 
      id: '3', 
      version: '1.2', 
      modified: '2023-03-20', 
      modifiedBy: 'Иван Петров',
      size: '1.4 MB',
      comment: 'Добавлено краткое содержание',
      versionNumber: 3,
      createdAt: '2023-03-20',
      createdBy: 'Иван Петров',
      comments: 'Добавлено краткое содержание'
    }
  ];

  const handleMetadataUpdate = (field: string, value: any) => {
    console.log('Updating metadata field:', field, value);
    toast({
      title: "Метаданные обновлены",
      description: `Поле ${field} обновлено`,
    });
  };

  return (
    <div className="h-full border-l bg-background overflow-hidden flex flex-col">
      <div className="flex justify-between items-center p-4 border-b bg-muted/30">
        <h2 className="text-lg font-medium">Детали документа</h2>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>
      
      <ScrollArea className="flex-1 h-0">
        <div className="p-6 space-y-6">
          <div className="flex flex-col items-center text-center">
            <div className="mb-4">
              {document.thumbnail ? (
                <img 
                  src={document.thumbnail} 
                  alt={document.name} 
                  className="max-h-28 object-contain" 
                />
              ) : renderIcon()}
            </div>
            
            <h3 className="text-lg font-medium">{document.name}</h3>
            <p className="text-sm text-muted-foreground">
              {isFolder ? 'Папка' : fileExtension}
            </p>
          </div>
          
          <div className="flex gap-2 justify-center">
            {!isFolder && (
              <Button variant="outline" size="sm">
                <Eye className="h-4 w-4 mr-2" />
                Просмотр
              </Button>
            )}
            
            {!isFolder && (
              <Button variant="outline" size="sm">
                <Edit className="h-4 w-4 mr-2" />
                Редактировать
              </Button>
            )}
            
            {!isFolder && (
              <Button variant="outline" size="sm">
                <Download className="h-4 w-4 mr-2" />
                Скачать
              </Button>
            )}
            
            <Button variant="outline" size="sm">
              <Share2 className="h-4 w-4 mr-2" />
              Поделиться
            </Button>
            
            <Button variant="outline" size="sm">
              <Star className="h-4 w-4 mr-2" />
              {document.favorited ? 'Убрать из избранного' : 'В избранное'}
            </Button>
            
            <Button variant="outline" size="sm" className="text-destructive border-destructive">
              <Trash className="h-4 w-4 mr-2" />
              Удалить
            </Button>
          </div>
          
          <Separator />

          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid grid-cols-3 mb-4">
              <TabsTrigger value="details">Свойства</TabsTrigger>
              <TabsTrigger value="versions">Версии</TabsTrigger>
              <TabsTrigger value="permissions">Доступ</TabsTrigger>
            </TabsList>
            
            <TabsContent value="details" className="space-y-6">
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Тип</span>
                  <span className="text-sm font-medium">
                    {isFolder ? 'Папка' : fileExtension}
                  </span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Размер</span>
                  <span className="text-sm font-medium">{document.size || 'Нет данных'}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Владелец</span>
                  <span className="text-sm font-medium">{document.owner}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Изменен</span>
                  <span className="text-sm font-medium">{format(modifiedDate, 'dd.MM.yyyy HH:mm')}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Расположение</span>
                  <span className="text-sm font-medium">{document.path || '/'}</span>
                </div>
              </div>
              
              <Separator />
              
              <CustomFieldsPanel 
                document={document} 
                onUpdate={handleMetadataUpdate}
              />
            </TabsContent>
            
            <TabsContent value="versions" className="space-y-6">
              <div className="space-y-4">
                <h3 className="text-sm font-medium">История версий</h3>
                <VersionHistoryList versions={versions} />
              </div>
            </TabsContent>
            
            <TabsContent value="permissions" className="space-y-6">
              <PermissionManager 
                documentId={document.id}
                onUpdatePermission={(userId, role) => {
                  console.log('Updated permission:', userId, role);
                  toast({
                    title: "Права доступа обновлены",
                    description: `Права для пользователя обновлены на: ${role}`,
                  });
                }}
              />
            </TabsContent>
          </Tabs>
          
          <Separator />
          
          <div>
            <h3 className="text-sm font-medium mb-2">Активность</h3>
            <div className="space-y-2">
              {activities.map(activity => (
                <ActivityItem key={activity.id} activity={activity} />
              ))}
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
