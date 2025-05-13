import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useToast } from "@/hooks/use-toast";
import { FileUploader } from "@/components/FileUploader";
import { FileUploadDialog } from "@/components/FileUploadDialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { DocumentGrid } from "@/components/DocumentGrid";
import { Document, DocumentType } from '@/types/document';
import { Upload, Loader2, Grid2X2, List } from 'lucide-react';
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

const FileUpload = () => {
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [category, setCategory] = useState<string>('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [selectedDestination, setSelectedDestination] = useState<'downloads' | 'new'>('downloads');
  const navigate = useNavigate();
  const { toast } = useToast();

  const handleUploadComplete = (fileNames: string[]) => {
    toast({
      title: "Файлы загружены",
      description: `${fileNames.length} файлов успешно загружено.`,
    });
  };

  const handleFileUpload = async () => {
    setIsUploading(true);
    setUploadProgress(0);

    // Simulate upload progress
    for (let i = 0; i <= 100; i += 10) {
      await new Promise(resolve => setTimeout(resolve, 200));
      setUploadProgress(i);
    }

    setIsUploading(false);
    toast({
      title: "Файлы загружены",
      description: "Ваши файлы успешно загружены в систему.",
    });
  };

  const handleRemoveFile = (index: number) => {
    const newFiles = [...uploadedFiles];
    newFiles.splice(index, 1);
    setUploadedFiles(newFiles);
  };

  const handleSelectDestination = (destination: 'downloads' | 'new') => {
    setSelectedDestination(destination);
    toast({
      title: "Папка выбрана",
      description: destination === 'downloads' ? "Выбрана папка Загрузки" : "Выбрана Новая папка",
    });
  };

  const handleCreateFolder = () => {
    toast({
      title: "Создание новой папки",
      description: "Функция создания новой папки будет реализована в будущем.",
    });
  };

  const handleUploadToDestination = () => {
    toast({
      title: "Загрузка файлов",
      description: `Файлы будут загружены в ${selectedDestination === 'downloads' ? 'Загрузки' : 'Новую папку'}.`,
    });
    setShowUploadDialog(false);
  };

  // Mock documents that represent uploaded files
  const uploadedDocuments: Document[] = uploadedFiles.map((file, index) => ({
    id: `temp-${index}`,
    name: file.name,
    type: file.name.split('.').pop()?.toLowerCase() as DocumentType || 'pdf',
    size: `${(file.size / (1024 * 1024)).toFixed(2)} MB`,
    modified: new Date().toISOString(),
    owner: 'Текущий пользователь',
    category: category || 'uncategorized',
  }));

  return (
    <div className="container mx-auto py-6 px-4 md:px-6">
      <div className="mb-6">
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink href="/">Документы</BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>Загрузка файлов</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </div>

      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-2">Загрузка файлов</h1>
        <p className="text-muted-foreground">
          Загрузите документы в систему
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Выберите файлы для загрузки</CardTitle>
              <CardDescription>
                Поддерживаемые форматы: PDF, DOC, XLSX, PPT, изображения
              </CardDescription>
            </CardHeader>
            <CardContent>
              <FileUploader 
                onUploadComplete={handleUploadComplete}
                maxFiles={5}
                acceptedFileTypes=".pdf,.doc,.docx,.xlsx,.ppt,.jpg,.png"
              />

              {uploadedFiles.length > 0 && (
                <div className="mt-4">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-medium">Выбранные файлы</h3>
                    <div className="flex items-center gap-2">
                      <ToggleGroup type="single" value={viewMode} onValueChange={(value) => value && setViewMode(value as 'grid' | 'list')}>
                        <ToggleGroupItem value="grid" aria-label="Сетка">
                          <Grid2X2 className="h-4 w-4" />
                        </ToggleGroupItem>
                        <ToggleGroupItem value="list" aria-label="Список">
                          <List className="h-4 w-4" />
                        </ToggleGroupItem>
                      </ToggleGroup>
                    </div>
                  </div>
                  
                  <DocumentGrid
                    documents={uploadedDocuments}
                    onDocumentClick={() => {}}
                    viewMode={viewMode}
                    selectedDocument={null}
                    onDocumentSelect={() => {}}
                  />
                </div>
              )}

              {isUploading && (
                <div className="mt-4">
                  <p className="text-sm mb-2">Загрузка: {uploadProgress}%</p>
                  <Progress value={uploadProgress} />
                </div>
              )}
            </CardContent>
            <CardFooter className="flex justify-between">
              <Button 
                variant="outline" 
                onClick={() => navigate('/')}
              >
                Отмена
              </Button>
              <Button 
                onClick={() => setShowUploadDialog(true)}
                disabled={uploadedFiles.length === 0 || isUploading}
              >
                {isUploading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Загрузка...
                  </>
                ) : (
                  <>
                    <Upload className="mr-2 h-4 w-4" />
                    Загрузить файлы
                  </>
                )}
              </Button>
            </CardFooter>
          </Card>
        </div>

        <div>
          <Card>
            <CardHeader>
              <CardTitle>Параметры загрузки</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="category">Категория</Label>
                  <Select value={category} onValueChange={setCategory}>
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите категорию" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectItem value="managers">Руководители</SelectItem>
                        <SelectItem value="development">Отдел развития</SelectItem>
                        <SelectItem value="procurement">Прокюрмент</SelectItem>
                        <SelectItem value="electrical">Электрические сети</SelectItem>
                        <SelectItem value="weakening">Слаботочные системы</SelectItem>
                        <SelectItem value="interface">Отдел интерфейс</SelectItem>
                        <SelectItem value="pse">PSE DCC</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>
                
                {/* Removed the automatic tagging and sharing after upload switches */}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Upload Dialog */}
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

export default FileUpload;
