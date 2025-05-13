
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Document } from '@/types/document';
import { ArrowDown, ArrowRight, File, Link2 } from 'lucide-react';

interface DocumentNode {
  id: string;
  name: string;
  type: string;
  children?: DocumentNode[];
  dependencies?: string[];
}

interface DocumentRelationshipMapProps {
  document?: Document;
  relatedDocuments?: Document[];
}

export function DocumentRelationshipMap({ document, relatedDocuments = [] }: DocumentRelationshipMapProps) {
  const [expanded, setExpanded] = React.useState<Record<string, boolean>>({});
  
  // Demo relationship structure
  const documentHierarchy: DocumentNode = {
    id: document?.id || 'root',
    name: document?.name || 'Текущий документ',
    type: document?.type || 'pdf',
    children: [
      {
        id: 'child1',
        name: 'Технические спецификации.pdf',
        type: 'pdf'
      },
      {
        id: 'child2',
        name: 'Схемы процессов.doc',
        type: 'doc',
        children: [
          {
            id: 'grandchild1',
            name: 'Детализация процесса.xlsx',
            type: 'xlsx'
          }
        ]
      }
    ],
    dependencies: ['dep1', 'dep2']
  };
  
  const toggleExpand = (id: string) => {
    setExpanded(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };
  
  const renderNode = (node: DocumentNode, level: number = 0) => {
    const isExpanded = expanded[node.id] || level === 0;
    const hasChildren = node.children && node.children.length > 0;
    
    return (
      <div key={node.id} className="mt-2">
        <div 
          className={`flex items-center p-2 rounded-md ${level === 0 ? 'bg-primary/10 font-medium' : 'hover:bg-accent'}`}
          style={{ marginLeft: `${level * 20}px` }}
        >
          {hasChildren && (
            <button onClick={() => toggleExpand(node.id)} className="mr-2 text-muted-foreground">
              {isExpanded ? (
                <ArrowDown className="h-4 w-4" />
              ) : (
                <ArrowRight className="h-4 w-4" />
              )}
            </button>
          )}
          
          {!hasChildren && <div className="w-6" />}
          
          <File className={`h-5 w-5 mr-2 ${getIconColor(node.type)}`} />
          
          <span className="flex-1 truncate">{node.name}</span>
          
          {node.dependencies && node.dependencies.length > 0 && (
            <div className="text-muted-foreground flex items-center">
              <Link2 className="h-4 w-4 mr-1" />
              <span className="text-xs">{node.dependencies.length}</span>
            </div>
          )}
        </div>
        
        {isExpanded && hasChildren && (
          <div>
            {node.children!.map(child => renderNode(child, level + 1))}
          </div>
        )}
      </div>
    );
  };
  
  const getIconColor = (type: string): string => {
    switch (type) {
      case 'pdf': return 'text-red-500';
      case 'doc': return 'text-blue-500';
      case 'xlsx': return 'text-green-500';
      case 'ppt': return 'text-orange-500';
      case 'image': return 'text-purple-500';
      default: return 'text-gray-500';
    }
  };
  
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center">
          <Link2 className="h-5 w-5 mr-2" />
          Связи документа
        </CardTitle>
      </CardHeader>
      <CardContent>
        {document ? (
          <div className="space-y-4">
            {renderNode(documentHierarchy)}
            
            <div className="mt-4 pt-4 border-t">
              <h4 className="text-sm font-medium mb-2">Зависимости</h4>
              <div className="space-y-2">
                <div className="flex items-center p-2 rounded-md hover:bg-accent">
                  <File className="h-5 w-5 mr-2 text-blue-500" />
                  <span className="flex-1 truncate">Отчет безопасности.pdf</span>
                </div>
                <div className="flex items-center p-2 rounded-md hover:bg-accent">
                  <File className="h-5 w-5 mr-2 text-green-500" />
                  <span className="flex-1 truncate">Данные измерений.xlsx</span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center text-muted-foreground py-4">
            Выберите документ для просмотра связей
          </div>
        )}
      </CardContent>
    </Card>
  );
}
