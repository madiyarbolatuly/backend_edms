
import React from 'react';
import { Document } from '@/types/document';
import { cn } from '@/lib/utils';
import { 
  FileText, File, FileSpreadsheet, 
  FileImage, Folder, MoreVertical, 
  Star, Download, Trash,
  Share2, CheckCircle2
} from 'lucide-react';
import { format } from 'date-fns';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface DocumentListItemProps {
  document: Document;
  onClick: (document: Document) => void;
  isSelected?: boolean;
  onSelect: () => void;
  multipleSelection?: boolean;
  onPreview?: (document: Document) => void;
  onEdit?: (document: Document) => void;
}

export function DocumentListItem({ 
  document, 
  onClick, 
  isSelected, 
  onSelect,
  multipleSelection = false,
  onPreview,
  onEdit
}: DocumentListItemProps) {
  const renderIcon = () => {
    switch (document.type) {
      case 'pdf':
        return <FileText className="h-5 w-5 text-red-500" />;
      case 'doc':
        return <FileText className="h-5 w-5 text-blue-500" />;
      case 'xlsx':
        return <FileSpreadsheet className="h-5 w-5 text-green-500" />;
      case 'image':
        return <FileImage className="h-5 w-5 text-purple-500" />;
      case 'folder':
        return <Folder className="h-5 w-5 text-yellow-500" />;
      default:
        return <File className="h-5 w-5 text-gray-500" />;
    }
  };

  const modifiedDate = new Date(document.modified);
  const formattedDate = format(modifiedDate, 'dd.MM.yyyy');
  const isFolder = document.type === 'folder';
  
  return (
    <div 
      className={cn(
        "flex items-center py-2 px-4 hover:bg-accent/50 border-b last:border-0",
        isSelected ? "bg-primary/5" : "bg-card"
      )}
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
      onDoubleClick={() => onClick(document)}
    >
      <div className="flex items-center gap-3 flex-1">
        <div className="flex-shrink-0">
          {isSelected ? (
            multipleSelection ? (
              <Checkbox checked className="h-5 w-5" />
            ) : (
              <CheckCircle2 className="h-5 w-5 text-primary" />
            )
          ) : renderIcon()}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center">
            <h3 className="font-medium truncate flex-1" title={document.name}>
              {document.name}
            </h3>
            {document.favorited && (
              <Star className="h-4 w-4 fill-yellow-400 text-yellow-400 ml-2" />
            )}
          </div>
        </div>
      </div>
      
      <div className="flex-shrink-0 text-sm text-muted-foreground w-32 px-2">
        {formattedDate}
      </div>
      
      <div className="flex-shrink-0 text-sm text-muted-foreground w-32 px-2 truncate">
        {document.owner}
      </div>
      
      <div className="flex-shrink-0 text-sm text-muted-foreground w-20 px-2">
        {document.size || '-'}
      </div>
      
      <div className="flex-shrink-0">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" onClick={(e) => e.stopPropagation()}>
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onClick(document)}>
              {isFolder ? 'Открыть' : 'Выбрать'}
            </DropdownMenuItem>
            {!isFolder && onPreview && (
              <DropdownMenuItem onClick={() => onPreview(document)}>
                Просмотр
              </DropdownMenuItem>
            )}
            {!isFolder && onEdit && (
              <DropdownMenuItem onClick={() => onEdit(document)}>
                Редактировать
              </DropdownMenuItem>
            )}
            {isFolder ? (
              <>
                <DropdownMenuItem>Новый файл</DropdownMenuItem>
                <DropdownMenuItem>Новая папка</DropdownMenuItem>
              </>
            ) : (
              <DropdownMenuItem>
                <Download className="h-4 w-4 mr-2" />
                Скачать
              </DropdownMenuItem>
            )}
            <DropdownMenuItem>
              <Share2 className="h-4 w-4 mr-2" />
              Поделиться
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-destructive">
              <Trash className="h-4 w-4 mr-2" />
              Удалить
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
