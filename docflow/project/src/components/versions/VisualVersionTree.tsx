
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Calendar, ChevronDown, ChevronRight, Download, Eye, GitBranch, History } from 'lucide-react';
import { Button } from '@/components/ui/button';

export interface VersionNode {
  id: string;
  version: string;
  date: string;
  author: string;
  status: 'draft' | 'approved' | 'deprecated';
  comment?: string;
  children?: VersionNode[];
}

const MOCK_VERSION_TREE: VersionNode = {
  id: 'v1.0',
  version: '1.0',
  date: '2023-06-15',
  author: 'Александр Петров',
  status: 'approved',
  comment: 'Первая утвержденная версия',
  children: [
    {
      id: 'v1.1',
      version: '1.1',
      date: '2023-08-20',
      author: 'Мария Иванова',
      status: 'approved',
      comment: 'Обновлены технические параметры',
      children: [
        {
          id: 'v1.2',
          version: '1.2',
          date: '2023-09-15',
          author: 'Андрей Смирнов',
          status: 'approved',
          comment: 'Добавлены схемы и чертежи',
          children: [
            {
              id: 'v2.0-draft1',
              version: '2.0-draft1',
              date: '2023-11-10',
              author: 'Елена Соколова',
              status: 'draft',
              comment: 'Черновик новой версии 2.0'
            },
            {
              id: 'v2.0-draft2',
              version: '2.0-draft2',
              date: '2023-11-20',
              author: 'Елена Соколова',
              status: 'draft',
              comment: 'Исправления по комментариям'
            }
          ]
        }
      ]
    },
    {
      id: 'v1.1.1',
      version: '1.1.1',
      date: '2023-08-25',
      author: 'Николай Петров',
      status: 'deprecated',
      comment: 'Исправление ошибок'
    }
  ]
};

interface VisualVersionTreeProps {
  currentVersion?: string;
  onVersionSelect?: (versionId: string) => void;
}

export function VisualVersionTree({ currentVersion, onVersionSelect }: VisualVersionTreeProps) {
  const [expandedNodes, setExpandedNodes] = React.useState<Record<string, boolean>>({
    'v1.0': true,
    'v1.1': true,
    'v1.2': true
  });

  const toggleNode = (nodeId: string) => {
    setExpandedNodes(prev => ({
      ...prev,
      [nodeId]: !prev[nodeId]
    }));
  };

  const getStatusBadge = (status: 'draft' | 'approved' | 'deprecated') => {
    switch (status) {
      case 'draft':
        return <Badge variant="outline" className="bg-blue-100 text-blue-800">Черновик</Badge>;
      case 'approved':
        return <Badge variant="outline" className="bg-green-100 text-green-800">Утверждено</Badge>;
      case 'deprecated':
        return <Badge variant="outline" className="bg-gray-100 text-gray-800">Устарело</Badge>;
      default:
        return null;
    }
  };

  const renderTreeNode = (node: VersionNode, depth: number = 0) => {
    const isExpanded = expandedNodes[node.id] || false;
    const hasChildren = node.children && node.children.length > 0;
    const isCurrentVersion = node.id === currentVersion;
    const formattedDate = new Date(node.date).toLocaleDateString('ru-RU');

    return (
      <div key={node.id} className="version-tree-node">
        <div 
          className={`flex items-center py-2 px-3 rounded-md hover:bg-accent/50 ${isCurrentVersion ? 'bg-primary/10' : ''}`}
          style={{ marginLeft: `${depth * 20}px` }}
        >
          {hasChildren ? (
            <button 
              onClick={() => toggleNode(node.id)}
              className="text-muted-foreground mr-2"
            >
              {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </button>
          ) : (
            <div className="w-6"></div>
          )}
          
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium">{node.version}</span>
              {getStatusBadge(node.status)}
              {isCurrentVersion && (
                <Badge variant="outline" className="bg-primary/20 text-primary">
                  Текущая
                </Badge>
              )}
            </div>
            
            <div className="text-sm text-muted-foreground mt-1">
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  {formattedDate}
                </span>
                <span>{node.author}</span>
              </div>
              {node.comment && <div className="mt-1">{node.comment}</div>}
            </div>
          </div>
          
          <div className="flex gap-2 ml-2">
            <Button variant="ghost" size="icon" onClick={() => onVersionSelect && onVersionSelect(node.id)}>
              <Eye className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon">
              <Download className="h-4 w-4" />
            </Button>
          </div>
        </div>
        
        {isExpanded && hasChildren && (
          <div className="version-tree-children">
            {node.children.map(child => renderTreeNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <Card className="version-tree">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center">
          <GitBranch className="h-5 w-5 mr-2" />
          История версий
        </CardTitle>
        <Button variant="ghost" size="sm" className="text-xs gap-1">
          <History className="h-4 w-4" />
          Показать все
        </Button>
      </CardHeader>
      <CardContent>
        <div className="version-tree-container">
          {renderTreeNode(MOCK_VERSION_TREE)}
        </div>
      </CardContent>
    </Card>
  );
}
