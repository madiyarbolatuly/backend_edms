
import React from 'react';
import { format } from 'date-fns';
import { Button } from '@/components/ui/button';
import { Download, RotateCcw } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Version } from '@/types/document';

interface VersionHistoryListProps {
  versions: Version[];
}

export function VersionHistoryList({ versions }: VersionHistoryListProps) {
  return (
    <div className="space-y-4">
      {versions.map((version, index) => (
        <div 
          key={version.id} 
          className={`p-3 border rounded-lg ${index === 0 ? 'bg-blue-50 border-blue-200' : ''}`}
        >
          <div className="flex justify-between items-start">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-medium">{version.version || `v${version.versionNumber}`}</span>
                {index === 0 && (
                  <Badge variant="outline" className="bg-blue-100 text-blue-800 text-xs">
                    Текущая
                  </Badge>
                )}
              </div>
              <p className="text-sm text-muted-foreground">
                {format(new Date(version.modified || version.createdAt), 'dd.MM.yyyy HH:mm')}
              </p>
              <p className="text-sm mt-1">
                <span className="text-muted-foreground">Автор:</span> {version.modifiedBy || version.createdBy}
              </p>
              {(version.comment || version.comments) && (
                <p className="text-sm mt-2 text-muted-foreground">
                  "{version.comment || version.comments}"
                </p>
              )}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm">
                <Download className="h-3 w-3 mr-1" />
                <span className="text-xs">Скачать</span>
              </Button>
              {index !== 0 && (
                <Button variant="outline" size="sm">
                  <RotateCcw className="h-3 w-3 mr-1" />
                  <span className="text-xs">Восстановить</span>
                </Button>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
