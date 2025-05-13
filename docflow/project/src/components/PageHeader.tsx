
import React from 'react';
import { SearchBar } from './SearchBar';
import { Button } from '@/components/ui/button';
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Grid2X2, List, RefreshCw, Upload } from 'lucide-react';
import { CategoryType } from '@/types/document';

interface PageHeaderProps {
  title: string;
  description?: string;
  children?: React.ReactNode;
  categoryType?: CategoryType;
  searchQuery?: string;
  setSearchQuery?: (query: string) => void;
  viewMode?: 'grid' | 'list';
  setViewMode?: (mode: 'grid' | 'list') => void;
}

export function PageHeader({ 
  title, 
  description,
  children,
  categoryType,
  searchQuery, 
  setSearchQuery,
  viewMode,
  setViewMode
}: PageHeaderProps) {
  const getCategoryDescription = (type?: CategoryType) => {
    if (!type) return description;
    
    switch (type) {
      case 'all':
        return 'Все документы в вашем рабочем пространстве';
      case 'recent':
        return 'Недавно открытые документы';
      case 'shared':
        return 'Документы, которыми поделились с вами';
      case 'favorites':
        return 'Ваши избранные документы';
      case 'trash':
        return 'Удаленные документы';
      default:
        return `Документы в категории ${type}`;
    }
  };

  // Если children предоставлен, просто отображаем их вместо стандартных кнопок
  const renderActions = () => {
    if (children) {
      return children;
    }
    
    return (
      <div className="flex gap-2">
        <Button variant="outline" className="flex items-center gap-2">
          <RefreshCw size={16} />
          <span>Обновить</span>
        </Button>
        <Button className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700">
          <Upload size={16} />
          <span>Загрузить</span>
        </Button>
      </div>
    );
  };

  return (
    <div className="pb-4 border-b">
      <div className="flex flex-col md:flex-row justify-between md:items-center gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold">{title}</h1>
          <p className="text-muted-foreground">{description || getCategoryDescription(categoryType)}</p>
        </div>
        {renderActions()}
      </div>

      {(searchQuery !== undefined && setSearchQuery && viewMode !== undefined && setViewMode) && (
        <div className="flex flex-col md:flex-row gap-4 justify-between items-start md:items-center">
          <SearchBar query={searchQuery} setQuery={setSearchQuery} />
          <div className="flex items-center gap-4">
            <ToggleGroup type="single" value={viewMode} onValueChange={(value) => value && setViewMode(value as 'grid' | 'list')}>
              <ToggleGroupItem value="grid" aria-label="Сетка">
                <Grid2X2 className="h-4 w-4 mr-1" />
                <span>Сетка</span>
              </ToggleGroupItem>
              <ToggleGroupItem value="list" aria-label="Список">
                <List className="h-4 w-4 mr-1" />
                <span>Список</span>
              </ToggleGroupItem>
            </ToggleGroup>
          </div>
        </div>
      )}
    </div>
  );
}
