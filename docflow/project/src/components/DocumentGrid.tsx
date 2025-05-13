
import React, { useState, useEffect } from 'react';
import { Document, MultipleSelectionActions } from '@/types/document';
import { DocumentCard } from './DocumentCard';
import { FolderPlus, Upload, Check, Trash, Download, Share2, X, Eye, Edit } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { DocumentListItem } from './DocumentListItem';
import { cn } from '@/lib/utils';
import { Checkbox } from '@/components/ui/checkbox';
import { useToast } from '@/hooks/use-toast';

interface DocumentGridProps {
  documents: Document[];
  onDocumentClick: (document: Document) => void;
  viewMode?: 'grid' | 'list';
  selectedDocument?: Document | null;
  onDocumentSelect: (document: Document) => void;
  multipleSelection?: boolean;
  selectionActions?: MultipleSelectionActions;
  onFolderOpen?: (folder: Document) => void;
  onPreviewFile?: (file: Document) => void;
  onEditFile?: (file: Document) => void;
}

export function DocumentGrid({ 
  documents, 
  onDocumentClick, 
  viewMode = 'grid',
  selectedDocument,
  onDocumentSelect,
  multipleSelection = false,
  selectionActions,
  onFolderOpen,
  onPreviewFile,
  onEditFile
}: DocumentGridProps) {
  const { toast } = useToast();
  // Sort documents: folders first, then files
  const sortedDocuments = [...documents].sort((a, b) => {
    if (a.type === 'folder' && b.type !== 'folder') return -1;
    if (a.type !== 'folder' && b.type === 'folder') return 1;
    return a.name.localeCompare(b.name);
  });
  
  // For shift+click functionality
  const [lastSelectedIndex, setLastSelectedIndex] = useState<number | null>(null);
  const [isShiftPressed, setIsShiftPressed] = useState(false);

  // Event listeners for shift key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Shift') {
        setIsShiftPressed(true);
      }
    };
    
    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === 'Shift') {
        setIsShiftPressed(false);
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, []);

  // Handle multi-selection with shift key
  const handleDocumentSelect = (document: Document, index: number) => {
    if (!multipleSelection || !selectionActions) {
      onDocumentSelect(document);
      return;
    }

    if (isShiftPressed && lastSelectedIndex !== null) {
      // Find all documents between lastSelectedIndex and current index
      const startIdx = Math.min(lastSelectedIndex, index);
      const endIdx = Math.max(lastSelectedIndex, index);
      
      const docsBetween = sortedDocuments.slice(startIdx, endIdx + 1);
      const idsToAdd = docsBetween.map(doc => doc.id).filter(id => !selectionActions.selectedIds.includes(id));
      
      // Add all documents in between to selection
      if (selectionActions.selectedIds.includes(document.id)) {
        onDocumentSelect(document); // Toggle current document
      } else {
        // Add all documents in between to selection
        idsToAdd.forEach(id => {
          const doc = sortedDocuments.find(d => d.id === id);
          if (doc) onDocumentSelect(doc);
        });
      }
    } else {
      // Regular toggle selection
      onDocumentSelect(document);
      setLastSelectedIndex(index);
    }
  };

  const handleFolderOpen = (folder: Document) => {
    if (onFolderOpen) {
      onFolderOpen(folder);
    } else {
      toast({
        title: "Открытие папки",
        description: `Открытие папки: ${folder.name}`,
      });
    }
  };

  const handlePreviewFile = (file: Document) => {
    if (onPreviewFile) {
      onPreviewFile(file);
    } else {
      toast({
        title: "Просмотр файла",
        description: `Просмотр файла: ${file.name}`,
      });
    }
  };

  const handleEditFile = (file: Document) => {
    if (onEditFile) {
      onEditFile(file);
    } else {
      toast({
        title: "Редактирование файла",
        description: `Редактирование файла: ${file.name}`,
      });
    }
  };

  const handleSelectAll = () => {
    selectionActions?.onSelectAll?.();
  };

  const handleClearSelection = () => {
    selectionActions?.onClearSelection?.();
  };

  if (!documents.length) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="bg-muted w-16 h-16 rounded-full flex items-center justify-center mb-4">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-8 w-8 text-muted-foreground"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
        </div>
        <h3 className="text-lg font-medium mb-1">Документы не найдены</h3>
        <p className="text-muted-foreground text-sm max-w-md">
          Нет документов, соответствующих вашим критериям поиска или фильтрам. Попробуйте изменить условия поиска или добавить новые документы.
        </p>
        <div className="flex gap-3 mt-6">
          <Button variant="outline" size="sm">
            <FolderPlus className="h-4 w-4 mr-2" />
            Создать папку
          </Button>
          <Button size="sm">
            <Upload className="h-4 w-4 mr-2" />
            Загрузить файлы
          </Button>
        </div>
      </div>
    );
  }

  // Render selection actions bar when items are selected
  const renderSelectionActionsBar = () => {
    if (!multipleSelection || !selectionActions || selectionActions.selectedIds.length === 0) return null;
    
    // Check if any selected item is a file (not a folder)
    const hasSelectedFiles = selectionActions.selectedIds.some(id => {
      const doc = documents.find(d => d.id === id);
      return doc && doc.type !== 'folder';
    });

    return (
      <div className="flex items-center justify-between bg-muted/50 p-2 rounded-md mb-4 sticky top-0 z-10 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <Checkbox 
            checked={selectionActions.selectedIds.length === documents.length}
            onCheckedChange={() => {
              if (selectionActions.selectedIds.length === documents.length) {
                handleClearSelection();
              } else {
                handleSelectAll();
              }
            }}
          />
          <span className="text-sm font-medium">
            {selectionActions.selectedIds.length} выбрано
          </span>
        </div>
        <div className="flex gap-2">
          {selectionActions.onClearSelection && (
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={handleClearSelection}
              className="flex items-center gap-1"
            >
              <X size={16} />
              <span className="hidden md:inline">Отмена</span>
            </Button>
          )}
          {hasSelectedFiles && onPreviewFile && (
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => {
                const selectedFile = documents.find(d => d.id === selectionActions.selectedIds[0] && d.type !== 'folder');
                if (selectedFile) handlePreviewFile(selectedFile);
              }}
              className="flex items-center gap-1"
            >
              <Eye size={16} />
              <span className="hidden md:inline">Просмотр</span>
            </Button>
          )}
          {hasSelectedFiles && onEditFile && (
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => {
                const selectedFile = documents.find(d => d.id === selectionActions.selectedIds[0] && d.type !== 'folder');
                if (selectedFile) handleEditFile(selectedFile);
              }}
              className="flex items-center gap-1"
            >
              <Edit size={16} />
              <span className="hidden md:inline">Редактировать</span>
            </Button>
          )}
          {selectionActions.onDownloadSelected && (
            <Button 
              variant="outline" 
              size="sm" 
              onClick={selectionActions.onDownloadSelected}
              className="flex items-center gap-1"
            >
              <Download size={16} />
              <span className="hidden md:inline">Скачать</span>
            </Button>
          )}
          {selectionActions.onShareSelected && (
            <Button 
              variant="outline" 
              size="sm" 
              onClick={selectionActions.onShareSelected}
              className="flex items-center gap-1"
            >
              <Share2 size={16} />
              <span className="hidden md:inline">Поделиться</span>
            </Button>
          )}
          {selectionActions.onRestoreSelected && (
            <Button 
              variant="outline" 
              size="sm" 
              onClick={selectionActions.onRestoreSelected}
              className="flex items-center gap-1"
            >
              <Check size={16} />
              <span className="hidden md:inline">Восстановить</span>
            </Button>
          )}
          {selectionActions.onDeleteSelected && (
            <Button 
              variant="destructive" 
              size="sm" 
              onClick={selectionActions.onDeleteSelected}
              className="flex items-center gap-1"
            >
              <Trash size={16} />
              <span className="hidden md:inline">Удалить</span>
            </Button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {renderSelectionActionsBar()}
      
      {viewMode === 'grid' ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {sortedDocuments.map((doc, index) => (
            <DocumentCard 
              key={doc.id} 
              document={doc} 
              onClick={doc.type === 'folder' ? handleFolderOpen : onDocumentClick}
              isSelected={
                multipleSelection && selectionActions
                  ? selectionActions.selectedIds.includes(doc.id)
                  : selectedDocument?.id === doc.id
              }
              onSelect={() => handleDocumentSelect(doc, index)}
              multipleSelection={multipleSelection}
              onPreview={doc.type !== 'folder' ? handlePreviewFile : undefined}
              onEdit={doc.type !== 'folder' ? handleEditFile : undefined}
            />
          ))}
        </div>
      ) : (
        <div className={cn("rounded-md border")}>
          {sortedDocuments.map((doc, index) => (
            <DocumentListItem 
              key={doc.id} 
              document={doc} 
              onClick={doc.type === 'folder' ? handleFolderOpen : onDocumentClick}
              isSelected={
                multipleSelection && selectionActions
                  ? selectionActions.selectedIds.includes(doc.id)
                  : selectedDocument?.id === doc.id
              }
              onSelect={() => handleDocumentSelect(doc, index)}
              multipleSelection={multipleSelection}
              onPreview={doc.type !== 'folder' ? handlePreviewFile : undefined}
              onEdit={doc.type !== 'folder' ? handleEditFile : undefined}
            />
          ))}
        </div>
      )}
    </div>
  );
}
