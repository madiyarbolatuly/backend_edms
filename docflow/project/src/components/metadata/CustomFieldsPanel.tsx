
import React, { useState } from 'react';
import { Document } from '@/types/document';
import { useToast } from '@/hooks/use-toast';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import {
  Command,
  CommandInput,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { Separator } from '@/components/ui/separator';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { CalendarIcon, Check, ChevronsUpDown } from 'lucide-react';

interface CustomFieldsProps {
  document: Document;
  onUpdate: (field: string, value: any) => void;
}

export function CustomFieldsPanel({ document, onUpdate }: CustomFieldsProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('');
  const [reviewDate, setReviewDate] = useState<Date | undefined>();
  const [isUrgent, setIsUrgent] = useState(false);
  const [assignedTo, setAssignedTo] = useState('');
  const [open, setOpen] = useState(false);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const { toast } = useToast();

  const people = [
    {
      value: "mikhail",
      label: "Михаил Иванов",
      department: "Руководители"
    },
    {
      value: "anna",
      label: "Анна Смирнова",
      department: "Отдел развития"
    },
    {
      value: "dmitry",
      label: "Дмитрий Козлов",
      department: "Прокюрмент"
    },
    {
      value: "elena",
      label: "Елена Соколова",
      department: "Электрические сети"
    },
    {
      value: "ivan",
      label: "Иван Петров",
      department: "Слаботочные системы"
    },
    {
      value: "olga",
      label: "Ольга Никитина",
      department: "Documentation Center-Документооборот"
    }
  ];

  const handleSubmit = () => {
    toast({
      title: "Метаданные обновлены",
      description: "Изменения сохранены и отправлены ответственным лицам",
    });

    // Update all metadata fields
    if (title) onUpdate('title', title);
    if (description) onUpdate('description', description);
    if (category) onUpdate('category', category);
    if (reviewDate) onUpdate('reviewDate', reviewDate);
    if (isUrgent) onUpdate('isUrgent', isUrgent);
    if (assignedTo) onUpdate('assignedTo', assignedTo);
  };

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium">Расширенные метаданные</h3>

      <div className="grid gap-3">
        <div>
          <label htmlFor="title" className="text-xs font-medium mb-1 block">
            Название
          </label>
          <Input 
            id="title"
            placeholder="Введите название"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>

        <div>
          <label htmlFor="description" className="text-xs font-medium mb-1 block">
            Описание
          </label>
          <Textarea 
            id="description"
            placeholder="Введите описание"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        <div>
          <label htmlFor="category" className="text-xs font-medium mb-1 block">
            Категория
          </label>
          <Select onValueChange={setCategory} value={category}>
            <SelectTrigger id="category">
              <SelectValue placeholder="Выберите категорию" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="finances">Финансы</SelectItem>
              <SelectItem value="contracts">Контракты</SelectItem>
              <SelectItem value="hr">HR</SelectItem>
              <SelectItem value="technical">Техническая документация</SelectItem>
              <SelectItem value="legal">Юридические документы</SelectItem>
              <SelectItem value="marketing">Маркетинг</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div>
          <label htmlFor="review-date" className="text-xs font-medium mb-1 block">
            Дата пересмотра
          </label>
          <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                id="review-date"
                className={cn(
                  "w-full justify-start text-left font-normal",
                  !reviewDate && "text-muted-foreground"
                )}
              >
                <CalendarIcon className="mr-2 h-4 w-4" />
                {reviewDate ? format(reviewDate, "PPP") : <span>Выберите дату</span>}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0">
              <Calendar
                mode="single"
                selected={reviewDate}
                onSelect={(date) => {
                  setReviewDate(date);
                  setCalendarOpen(false);
                }}
              />
            </PopoverContent>
          </Popover>
        </div>

        <div>
          <label htmlFor="assigned-to" className="text-xs font-medium mb-1 block">
            Ответственный
          </label>
          <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                role="combobox"
                aria-expanded={open}
                className="w-full justify-between"
                id="assigned-to"
              >
                {assignedTo
                  ? people.find((person) => person.value === assignedTo)?.label
                  : "Выберите сотрудника..."}
                <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-full p-0">
              <Command>
                <CommandInput placeholder="Поиск сотрудника..." />
                <CommandList>
                  <CommandEmpty>Нет результатов.</CommandEmpty>
                  <CommandGroup>
                    {people.map((person) => (
                      <CommandItem
                        key={person.value}
                        value={person.value}
                        onSelect={(currentValue) => {
                          setAssignedTo(currentValue === assignedTo ? "" : currentValue);
                          setOpen(false);
                        }}
                      >
                        <Check
                          className={cn(
                            "mr-2 h-4 w-4",
                            assignedTo === person.value ? "opacity-100" : "opacity-0"
                          )}
                        />
                        <div className="flex flex-col">
                          <span>{person.label}</span>
                          <span className="text-xs text-muted-foreground">{person.department}</span>
                        </div>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
        </div>

        <div className="flex items-center space-x-2">
          <Switch 
            id="urgent" 
            checked={isUrgent} 
            onCheckedChange={setIsUrgent}
          />
          <label htmlFor="urgent" className="text-xs font-medium">
            Срочно
          </label>
        </div>

        <Button onClick={handleSubmit} className="mt-2">Подтвердить</Button>
      </div>
    </div>
  );
}
