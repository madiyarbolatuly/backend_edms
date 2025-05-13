
import React from 'react';
import { cn } from '@/lib/utils';
import { 
  FileText, Clock, Users, Star, Trash2, 
  Settings, PlusCircle, 
  HardDrive, Folder, FolderOpen
} from 'lucide-react';
import { CategoryType } from '@/types/document';

interface SidebarProps {
  activeCategory: CategoryType;
  onCategoryChange: (category: CategoryType) => void;
}

interface SidebarItem {
  id: CategoryType;
  label: string;
  icon: React.ReactNode;
}

export function Sidebar({ activeCategory, onCategoryChange }: SidebarProps) {
  const mainNavItems: SidebarItem[] = [
    { id: 'all', label: 'Все документы', icon: <FileText size={18} /> },
    { id: 'recent', label: 'Недавние', icon: <Clock size={18} /> },
    { id: 'shared', label: 'Общий доступ', icon: <Users size={18} /> },
    { id: 'favorites', label: 'Избранное', icon: <Star size={18} /> },
    { id: 'trash', label: 'Корзина', icon: <Trash2 size={18} /> },
  ];

  const categoryItems: SidebarItem[] = [
    { id: 'managers', label: 'Руководители', icon: <FolderOpen size={18} /> },
    { id: 'development', label: 'Отдел развития', icon: <FolderOpen size={18} /> },
    { id: 'procurement', label: 'Прокюрмент', icon: <FolderOpen size={18} /> },
    { id: 'electrical', label: 'Электрические сети', icon: <FolderOpen size={18} /> },
    { id: 'weakening', label: 'Слаботочные системы', icon: <FolderOpen size={18} /> },
    { id: 'interface', label: 'Отдел интерфейс', icon: <FolderOpen size={18} /> },
    { id: 'pse', label: 'PSE DCC', icon: <FolderOpen size={18} /> },
  ];

  return (
    <div className="w-64 flex-shrink-0 h-screen bg-sidebar border-r border-sidebar-border hidden md:block">
      <div className="p-5">
        <div className="flex items-center gap-2 mb-8">
          <HardDrive className="h-6 w-6 text-primary" />
          <h1 className="text-xl font-bold">EDMS</h1>
        </div>

        <button className="w-full flex items-center gap-2 bg-primary hover:bg-primary/90 text-primary-foreground py-2 px-3 rounded-md mb-6 transition-colors">
          <PlusCircle size={18} />
          <span>Новый документ</span>
        </button>

        <nav className="space-y-1">
          {mainNavItems.map((item) => (
            <button
              key={item.id}
              onClick={() => onCategoryChange(item.id)}
              className={cn(
                "sidebar-item w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm",
                activeCategory === item.id ? "active" : ""
              )}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="mt-8 mb-2">
          <h2 className="text-xs uppercase tracking-wider text-muted-foreground font-semibold px-3 mb-2">
            Категории
          </h2>
          <nav className="space-y-1">
            {categoryItems.map((item) => (
              <button
                key={item.id}
                onClick={() => onCategoryChange(item.id)}
                className={cn(
                  "sidebar-item w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm",
                  activeCategory === item.id ? "active bg-gray-100 dark:bg-gray-800" : ""
                )}
              >
                {item.icon}
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
        </div>
      </div>

      <div className="absolute bottom-0 w-64 p-4 border-t border-sidebar-border">
        <button className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-sidebar-accent rounded-md transition-colors">
          <Settings size={18} />
          <span>Настройки</span>
        </button>
      </div>
    </div>
  );
}
