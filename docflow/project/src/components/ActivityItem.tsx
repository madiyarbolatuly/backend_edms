
import React from 'react';
import { Eye, FileEdit, MessageSquare, Upload, Download, Trash, RefreshCw, Share } from 'lucide-react';
import { format } from 'date-fns';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';

export interface Activity {
  id: string;
  user: string;
  action: 'viewed' | 'modified' | 'commented' | 'uploaded' | 'deleted' | 'restored' | 'downloaded' | 'shared';
  date: string;
  timestamp?: string; // Added to support both date and timestamp fields
}

interface ActivityItemProps {
  activity: Activity;
}

export function ActivityItem({ activity }: ActivityItemProps) {
  const getIcon = () => {
    switch (activity.action) {
      case 'viewed':
        return <Eye className="h-4 w-4 text-blue-500" />;
      case 'modified':
        return <FileEdit className="h-4 w-4 text-amber-500" />;
      case 'commented':
        return <MessageSquare className="h-4 w-4 text-purple-500" />;
      case 'uploaded':
        return <Upload className="h-4 w-4 text-green-500" />;
      case 'downloaded':
        return <Download className="h-4 w-4 text-blue-500" />;
      case 'deleted':
        return <Trash className="h-4 w-4 text-red-500" />;
      case 'restored':
        return <RefreshCw className="h-4 w-4 text-green-500" />;
      case 'shared':
        return <Share className="h-4 w-4 text-indigo-500" />;
      default:
        return <FileEdit className="h-4 w-4 text-gray-500" />;
    }
  };

  const getActionText = () => {
    switch (activity.action) {
      case 'viewed':
        return 'просмотрел(а) документ';
      case 'modified':
        return 'изменил(а) документ';
      case 'commented':
        return 'добавил(а) комментарий';
      case 'uploaded':
        return 'загрузил(а) документ';
      case 'deleted':
        return 'удалил(а) документ';
      case 'restored':
        return 'восстановил(а) документ';
      case 'downloaded':
        return 'скачал(а) документ';
      case 'shared':
        return 'поделился(лась) документом';
      default:
        return 'взаимодействовал(а) с документом';
    }
  };
  
  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(part => part[0])
      .join('')
      .toUpperCase();
  };

  return (
    <div className="flex items-start gap-3 p-3 border-b last:border-b-0 hover:bg-accent/30 transition-colors rounded-md">
      <Avatar className="h-8 w-8 border">
        <AvatarFallback className="bg-primary/10 text-primary">
          {getInitials(activity.user)}
        </AvatarFallback>
      </Avatar>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm">{activity.user}</span>
          <div className="bg-primary/10 rounded-full p-1.5">
            {getIcon()}
          </div>
        </div>
        <p className="text-sm">
          {getActionText()}
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          {format(new Date(activity.date || activity.timestamp || ''), 'dd.MM.yyyy HH:mm')}
        </p>
      </div>
    </div>
  );
}
