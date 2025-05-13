
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { 
  FileText, FileSpreadsheet, FileImage, File, 
  MoreHorizontal, Download, Share2, Trash
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ActivityItem } from '@/components/ActivityItem';
import { MetadataCard } from '@/components/MetadataCard';
import { Document, ActivityAction, Version } from '@/types/document';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

import { CustomFieldsPanel } from '@/components/metadata/CustomFieldsPanel';
import { DocumentRelationshipMap } from '@/components/relationships/DocumentRelationshipMap';
import { VisualVersionTree } from '@/components/versions/VisualVersionTree';
import { DocumentComparison } from '@/components/versions/DocumentComparison';
import { PermissionManager } from '@/components/permissions/PermissionManager';
import { ApprovalWorkflow } from '@/components/approvals/ApprovalWorkflow';
import { DocumentAnnotations } from '@/components/annotations/DocumentAnnotations';
import { VersionHistoryList } from '@/components/VersionHistoryList';

interface Activity {
  id: string;
  action: ActivityAction;
  timestamp: string;
  user: string;
  date: string;
}

const MOCK_ACTIVITIES: Activity[] = [
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
  },
  {
    id: '5',
    action: "downloaded",
    timestamp: new Date(Date.now() - 345600000).toISOString(),
    user: 'Александр Иванов',
    date: new Date(Date.now() - 345600000).toISOString()
  }
];

const MOCK_VERSIONS: Version[] = [
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
  },
];

const MOCK_DOCUMENT: Document =   {
  id: '1',
  name: 'Годовой отчет 2023.pdf',
  type: 'pdf',
  size: '4.2 MB',
  modified: new Date(Date.now() - 3600000).toISOString(),
  owner: 'Александр Иванов',
  category: 'reports',
  favorited: true
};

const DocumentDetails = () => {
  const { id } = useParams<{ id: string }>();
  const [document, setDocument] = useState<Document | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [activeTab, setActiveTab] = useState('details');

  useEffect(() => {
    setTimeout(() => {
      setDocument(MOCK_DOCUMENT);
      setActivities(MOCK_ACTIVITIES);
    }, 500);
  }, [id]);

  const handleMetadataUpdate = (field: string, value: any) => {
    console.log('Updating metadata field:', field, value);
    // In a real application, you would save this to your backend
  };

  return (
    <div className="flex flex-col h-screen">
      <div className="flex-1 overflow-auto">
        <div className="container mx-auto py-6 px-4 md:px-6">
          <div className="mb-6">
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem>
                  <BreadcrumbLink href="/">Документы</BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  <BreadcrumbPage>{document?.name || 'Загрузка...'}</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-2 space-y-6">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle>{document?.name || 'Загрузка...'}</CardTitle>
                    <CardDescription>
                      {document?.type.toUpperCase()} • {document?.size} • Обновлено {document?.modified ? new Date(document.modified).toLocaleDateString() : '...'}
                    </CardDescription>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreHorizontal className="h-5 w-5" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem>
                        <Download className="mr-2 h-4 w-4" />
                        <span>Скачать</span>
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Share2 className="mr-2 h-4 w-4" />
                        <span>Поделиться</span>
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem className="text-destructive">
                        <Trash className="mr-2 h-4 w-4" />
                        <span>Удалить</span>
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </CardHeader>
                <CardContent>
                  <div className="flex justify-center p-6 bg-accent rounded-md">
                    {document?.type === 'pdf' && (
                      <FileText className="h-40 w-40 text-primary" />
                    )}
                    {document?.type === 'doc' && (
                      <FileText className="h-40 w-40 text-blue-500" />
                    )}
                    {document?.type === 'xlsx' && (
                      <FileSpreadsheet className="h-40 w-40 text-green-500" />
                    )}
                    {document?.type === 'ppt' && (
                      <File className="h-40 w-40 text-orange-500" />
                    )}
                    {document?.type === 'image' && (
                      <FileImage className="h-40 w-40 text-purple-500" />
                    )}
                  </div>
                </CardContent>
              </Card>

              <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList className="grid grid-cols-4 mb-6">
                  <TabsTrigger value="details">Детали</TabsTrigger>
                  <TabsTrigger value="versions">Версии</TabsTrigger>
                  <TabsTrigger value="permissions">Доступ</TabsTrigger>
                  <TabsTrigger value="annotations">Комментарии</TabsTrigger>
                </TabsList>
                
                <TabsContent value="details" className="space-y-6">
                  <CustomFieldsPanel 
                    document={document || undefined} 
                    onUpdate={handleMetadataUpdate}
                  />
                  
                  <DocumentRelationshipMap 
                    document={document || undefined} 
                    relatedDocuments={[]} 
                  />
                </TabsContent>
                
                <TabsContent value="versions" className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle>История версий</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <VersionHistoryList versions={MOCK_VERSIONS} />
                    </CardContent>
                  </Card>
                  
                  <VisualVersionTree 
                    currentVersion="v1.2"
                    onVersionSelect={(versionId) => console.log('Selected version:', versionId)}
                  />
                  
                  <DocumentComparison documentId={id} />
                </TabsContent>
                
                <TabsContent value="permissions" className="space-y-6">
                  <PermissionManager 
                    documentId={id}
                    onUpdatePermission={(userId, role) => console.log('Updated permission:', userId, role)}
                  />
                  
                  <ApprovalWorkflow documentId={id} />
                </TabsContent>
                
                <TabsContent value="annotations" className="space-y-6">
                  <DocumentAnnotations documentId={id} />
                </TabsContent>
              </Tabs>
            </div>

            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Метаданные</CardTitle>
                  <CardDescription>Информация о документе</CardDescription>
                </CardHeader>
                <CardContent>
                  <MetadataCard document={document} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Активность</CardTitle>
                  <CardDescription>Недавние действия с документом</CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                  <ScrollArea className="h-[300px]">
                    {activities.map(activity => (
                      <ActivityItem key={activity.id} activity={activity} />
                    ))}
                  </ScrollArea>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DocumentDetails;
