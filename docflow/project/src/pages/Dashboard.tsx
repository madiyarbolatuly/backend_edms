import React, { useState } from 'react';
import { SearchBar } from '@/components/SearchBar';
import { PageHeader } from '@/components/PageHeader';
import { DocumentGrid } from '@/components/DocumentGrid';
import { Sidebar } from '@/components/Sidebar';
import { Document, CategoryType } from '@/types/document';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { FileText, Upload, Download, Users, HardDrive, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { FileUploadDialog } from '@/components/FileUploadDialog';
import { useToast } from '@/hooks/use-toast';

// Mock documents data
const MOCK_DOCUMENTS: Document[] = [
  {
    id: '1',
    name: 'Annual Report 2023.pdf',
    type: 'pdf',
    size: '4.2 MB',
    modified: new Date(Date.now() - 3600000).toISOString(),
    owner: 'Alex Johnson',
    category: 'reports',
    favorited: true
  },
  {
    id: '2',
    name: 'Project Proposal.doc',
    type: 'doc',
    size: '2.7 MB',
    modified: new Date(Date.now() - 86400000).toISOString(),
    owner: 'Sarah Miller',
    category: 'projects'
  },
  {
    id: '3',
    name: 'Financial Analysis.xlsx',
    type: 'xlsx',
    size: '1.8 MB',
    modified: new Date(Date.now() - 172800000).toISOString(),
    owner: 'David Chen',
    category: 'finance'
  },
  {
    id: '4',
    name: 'Marketing Presentation.ppt',
    type: 'ppt',
    size: '5.3 MB',
    modified: new Date(Date.now() - 259200000).toISOString(),
    owner: 'Emily Wang',
    category: 'marketing',
    shared: true
  },
  {
    id: '5',
    name: 'Product Roadmap.pdf',
    type: 'pdf',
    size: '3.1 MB',
    modified: new Date(Date.now() - 345600000).toISOString(),
    owner: 'Alex Johnson',
    category: 'products'
  },
  {
    id: '6',
    name: 'Design Assets',
    type: 'folder',
    modified: new Date(Date.now() - 432000000).toISOString(),
    owner: 'Michelle Lee',
    category: 'design'
  }
];

// Mock analytics data
const activityData = [
  { name: 'Пн', uploads: 4, downloads: 2, views: 8 },
  { name: 'Вт', uploads: 3, downloads: 5, views: 10 },
  { name: 'Ср', uploads: 5, downloads: 3, views: 12 },
  { name: 'Чт', uploads: 2, downloads: 6, views: 9 },
  { name: 'Пт', uploads: 6, downloads: 4, views: 15 },
  { name: 'Сб', uploads: 1, downloads: 2, views: 5 },
  { name: 'Вс', uploads: 0, downloads: 1, views: 3 }
];

const Dashboard = () => {
  const [activeCategory, setActiveCategory] = useState<CategoryType>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const navigate = useNavigate();
  const { toast } = useToast();

  const filteredDocuments = MOCK_DOCUMENTS.filter(doc => {
    const matchesSearch = doc.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = activeCategory === 'all' || 
                            activeCategory === 'recent' || 
                            activeCategory === 'shared' && doc.shared ||
                            activeCategory === 'favorites' && doc.favorited ||
                            doc.category === activeCategory;
    
    return matchesSearch && matchesCategory;
  });

  const handleDocumentClick = (document: Document) => {
    navigate(`/document/${document.id}`);
  };

  const handleDocumentSelect = (document: Document) => {
    setSelectedDocument(document);
  };

  const handleSelectDestination = (destination: 'downloads' | 'new') => {
    toast({
      title: "Папка выбрана",
      description: destination === 'downloads' ? "Выбрана папка Загрузки" : "Выбрана Новая папка",
    });
  };

  const handleCreateFolder = () => {
    toast({
      title: "Обновление",
      description: "Список файлов обновлен.",
    });
  };

  const handleUploadToDestination = () => {
    toast({
      title: "Загрузка файлов",
      description: "Переход на страницу загрузки файлов.",
    });
    setShowUploadDialog(false);
    navigate('/upload');
  };

  return (
    <div className="flex h-screen bg-background">
      <Sidebar activeCategory={activeCategory} onCategoryChange={setActiveCategory} />
      
      <div className="flex-1 overflow-auto">
        <div className="p-6">
          <PageHeader 
            title={activeCategory === 'all' ? 'Панель управления' : activeCategory.charAt(0).toUpperCase() + activeCategory.slice(1)}
            categoryType={activeCategory}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            viewMode={viewMode}
            setViewMode={setViewMode}
          >
            <div className="flex gap-2">
              <Button 
                variant="outline" 
                className="flex items-center gap-2"
                onClick={() => {}}
              >
                <RefreshCw className="h-4 w-4" />
                Обновить
              </Button>
              <Button 
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700"
                onClick={() => setShowUploadDialog(true)}
              >
                <Upload className="h-4 w-4" />
                Загрузить
              </Button>
            </div>
          </PageHeader>
          
          {activeCategory === 'all' && (
            <div className="mb-8">
              <h2 className="text-xl font-bold mb-4">Обзор аналитики</h2>
              
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Всего документов</CardTitle>
                    <FileText className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">127</div>
                    <p className="text-xs text-muted-foreground">+5 за последнюю неделю</p>
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Всего загрузок</CardTitle>
                    <Upload className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">24</div>
                    <p className="text-xs text-muted-foreground">+12 за последнюю неделю</p>
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Использовано места</CardTitle>
                    <HardDrive className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">4.2 ГБ</div>
                    <p className="text-xs text-muted-foreground">из 10 ГБ (42%)</p>
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Активных пользователей</CardTitle>
                    <Users className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">15</div>
                    <p className="text-xs text-muted-foreground">+3 за последнюю неделю</p>
                  </CardContent>
                </Card>
              </div>
              
              <Card className="mb-6">
                <CardHeader>
                  <CardTitle>Недельная активность</CardTitle>
                  <CardDescription>Взаимодействия с документами за последнюю неделю</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={activityData}
                        margin={{ top: 10, right: 30, left: 0, bottom: 20 }}
                      >
                        <XAxis dataKey="name" />
                        <YAxis />
                        <Tooltip />
                        <Bar dataKey="views" fill="#8884d8" name="Просмотры" />
                        <Bar dataKey="uploads" fill="#82ca9d" name="Загрузки" />
                        <Bar dataKey="downloads" fill="#ffc658" name="Скачивания" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
              
              <h2 className="text-xl font-bold mb-4">Недавние документы</h2>
            </div>
          )}
          
          <DocumentGrid 
            documents={filteredDocuments} 
            onDocumentClick={handleDocumentClick}
            viewMode={viewMode}
            selectedDocument={selectedDocument}
            onDocumentSelect={handleDocumentSelect}
          />
        </div>
      </div>
      
      <FileUploadDialog 
        open={showUploadDialog}
        onOpenChange={setShowUploadDialog}
        onSelectDestination={handleSelectDestination}
        onCreateFolder={handleCreateFolder}
        onUpload={handleUploadToDestination}
      />
    </div>
  );
};

export default Dashboard;
