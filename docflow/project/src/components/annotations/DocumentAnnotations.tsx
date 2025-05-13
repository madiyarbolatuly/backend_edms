
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { MessageSquare, Send } from 'lucide-react';
import { format } from 'date-fns';

interface Comment {
  id: string;
  user: {
    name: string;
    avatar?: string;
  };
  text: string;
  timestamp: string;
  replies?: Comment[];
}

// Mock comments for the document
const MOCK_COMMENTS: Comment[] = [
  {
    id: 'c1',
    user: {
      name: 'Алексей Петров',
      avatar: '/assets/avatars/avatar1.jpg',
    },
    text: 'Пожалуйста, обновите данные по максимальной нагрузке в таблице 3',
    timestamp: '2023-10-18T10:30:00',
    replies: [
      {
        id: 'c1-r1',
        user: {
          name: 'Мария Иванова',
          avatar: '/assets/avatars/avatar2.jpg',
        },
        text: 'Данные обновлены согласно последним измерениям',
        timestamp: '2023-10-18T11:15:00',
      }
    ]
  },
  {
    id: 'c2',
    user: {
      name: 'Николай Смирнов',
      avatar: '/assets/avatars/avatar3.jpg',
    },
    text: 'В разделе безопасности необходимо добавить ссылки на новые нормативы',
    timestamp: '2023-10-17T15:45:00',
  },
];

interface DocumentAnnotationsProps {
  documentId?: string;
}

export function DocumentAnnotations({ documentId }: DocumentAnnotationsProps) {
  const [comments, setComments] = React.useState<Comment[]>(MOCK_COMMENTS);
  const [newComment, setNewComment] = React.useState('');
  const [replyingTo, setReplyingTo] = React.useState<string | null>(null);

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(part => part[0])
      .join('')
      .toUpperCase();
  };

  const handleAddComment = () => {
    if (!newComment.trim()) return;

    if (replyingTo) {
      const updatedComments = comments.map(comment => {
        if (comment.id === replyingTo) {
          return {
            ...comment,
            replies: [
              ...(comment.replies || []),
              {
                id: `${comment.id}-r${(comment.replies?.length || 0) + 1}`,
                user: {
                  name: 'Текущий пользователь',
                },
                text: newComment,
                timestamp: new Date().toISOString(),
              }
            ]
          };
        }
        return comment;
      });
      
      setComments(updatedComments);
      setReplyingTo(null);
    } else {
      const newCommentObj: Comment = {
        id: `c${comments.length + 1}`,
        user: {
          name: 'Текущий пользователь',
        },
        text: newComment,
        timestamp: new Date().toISOString(),
      };
      
      setComments([...comments, newCommentObj]);
    }
    
    setNewComment('');
  };

  const handleReply = (commentId: string) => {
    setReplyingTo(commentId);
  };

  const formatTimestamp = (timestamp: string) => {
    return format(new Date(timestamp), 'dd.MM.yyyy HH:mm');
  };

  const renderCommentBlock = (comment: Comment, isReply = false) => {
    return (
      <div key={comment.id} className={`${isReply ? 'ml-8 mt-3 border-l-2 pl-4 border-accent' : 'mb-4'}`}>
        <div className="flex items-start">
          <Avatar className="h-8 w-8 mr-3">
            {comment.user.avatar && <AvatarImage src={comment.user.avatar} alt={comment.user.name} />}
            <AvatarFallback>{getInitials(comment.user.name)}</AvatarFallback>
          </Avatar>
          
          <div className="flex-1">
            <div className="flex items-center">
              <span className="font-medium">{comment.user.name}</span>
              <span className="text-xs text-muted-foreground ml-2">
                {formatTimestamp(comment.timestamp)}
              </span>
            </div>
            
            <div className="mt-1">{comment.text}</div>
            
            {!isReply && (
              <Button 
                variant="ghost" 
                size="sm" 
                className="mt-1 h-6 text-xs"
                onClick={() => handleReply(comment.id)}
              >
                Ответить
              </Button>
            )}
          </div>
        </div>
        
        {comment.replies?.map(reply => renderCommentBlock(reply, true))}
      </div>
    );
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center">
          <MessageSquare className="h-5 w-5 mr-2" />
          Комментарии и аннотации
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="comments-container">
          {comments.length > 0 ? (
            comments.map(comment => renderCommentBlock(comment))
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              Нет комментариев к документу
            </div>
          )}
        </div>
        
        <div className="comment-input-area">
          <div className="flex items-center mb-2">
            <Avatar className="h-8 w-8 mr-2">
              <AvatarFallback>ТП</AvatarFallback>
            </Avatar>
            {replyingTo && (
              <div className="flex items-center text-xs bg-accent/50 rounded px-2 py-1">
                <span>Ответ на комментарий</span>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="h-6 px-1 ml-1"
                  onClick={() => setReplyingTo(null)}
                >
                  ×
                </Button>
              </div>
            )}
          </div>
          
          <div className="flex gap-2">
            <Textarea
              placeholder="Добавить комментарий..."
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              className="min-h-[80px]"
            />
          </div>
          <div className="flex justify-end mt-2">
            <Button onClick={handleAddComment}>
              <Send className="h-4 w-4 mr-2" />
              Отправить
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
