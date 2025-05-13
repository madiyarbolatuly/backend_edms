
import React from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Calendar } from "@/components/ui/calendar";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
  SheetFooter,
} from "@/components/ui/sheet";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BookmarkIcon, CalendarIcon, Filter, Save, Search as SearchIcon, User2 } from 'lucide-react';
import { cn } from "@/lib/utils";
import { format } from "date-fns";

interface AdvancedSearchProps {
  onSearch?: (params: any) => void;
}

export function AdvancedSearch({ onSearch }: AdvancedSearchProps) {
  const [searchQuery, setSearchQuery] = React.useState('');
  const [documentType, setDocumentType] = React.useState('');
  const [department, setDepartment] = React.useState('');
  const [engineer, setEngineer] = React.useState('');
  const [dateFrom, setDateFrom] = React.useState<Date | undefined>(undefined);
  const [dateTo, setDateTo] = React.useState<Date | undefined>(undefined);
  
  const [savedSearches, setSavedSearches] = React.useState([
    { id: '1', name: 'Последние технические отчеты', query: 'тип:pdf отдел:технический' },
    { id: '2', name: 'Документы на согласовании', query: 'статус:согласование' }
  ]);
  
  const [dateFromOpen, setDateFromOpen] = React.useState(false);
  const [dateToOpen, setDateToOpen] = React.useState(false);
  
  const handleSearch = () => {
    if (onSearch) {
      onSearch({
        query: searchQuery,
        documentType,
        department,
        engineer,
        dateFrom,
        dateTo
      });
    }
  };
  
  const handleSaveSearch = () => {
    const newSearch = {
      id: Math.random().toString(),
      name: `Поиск ${savedSearches.length + 1}`,
      query: `${searchQuery} ${documentType ? `тип:${documentType}` : ''} ${department ? `отдел:${department}` : ''}`
    };
    
    setSavedSearches([...savedSearches, newSearch]);
  };
  
  const loadSavedSearch = (searchId: string) => {
    const search = savedSearches.find(s => s.id === searchId);
    if (search) {
      setSearchQuery(search.query);
    }
  };
  
  const handleApplyFilters = () => {
    handleSearch();
  };
  
  const clearFilters = () => {
    setDocumentType('');
    setDepartment('');
    setEngineer('');
    setDateFrom(undefined);
    setDateTo(undefined);
  };
  
  const getSuggestedQueries = () => [
    "Показать все документы на согласовании",
    "Технические отчеты за последний месяц",
    "Документы отдела закупок",
    "Показать просроченные задачи"
  ];

  return (
    <div className="w-full">
      <div className="relative">
        <SearchIcon className="absolute left-3 top-2.5 h-5 w-5 text-muted-foreground" />
        <Input
          placeholder="Поиск документов, задач, людей..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10 pr-32"
        />
        <div className="absolute right-1 top-1">
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="ghost" size="sm" className="gap-1">
                <Filter className="h-4 w-4" />
                Фильтры
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-[400px]">
              <SheetHeader>
                <SheetTitle>Расширенный поиск</SheetTitle>
                <SheetDescription>
                  Настройте параметры поиска для более точных результатов
                </SheetDescription>
              </SheetHeader>
              
              <div className="py-6 space-y-6">
                <div className="space-y-2">
                  <Label>Тип документа</Label>
                  <Select value={documentType} onValueChange={setDocumentType}>
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите тип" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="pdf">PDF</SelectItem>
                      <SelectItem value="doc">Word</SelectItem>
                      <SelectItem value="xlsx">Excel</SelectItem>
                      <SelectItem value="ppt">PowerPoint</SelectItem>
                      <SelectItem value="image">Изображение</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label>Отдел</Label>
                  <Select value={department} onValueChange={setDepartment}>
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите отдел" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="technical">Технический</SelectItem>
                      <SelectItem value="safety">Безопасность</SelectItem>
                      <SelectItem value="procurement">Закупки</SelectItem>
                      <SelectItem value="operations">Операционный</SelectItem>
                      <SelectItem value="quality">Контроль качества</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label>Ответственный инженер</Label>
                  <Select value={engineer} onValueChange={setEngineer}>
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите инженера" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="user1">Алексей Петров</SelectItem>
                      <SelectItem value="user2">Мария Иванова</SelectItem>
                      <SelectItem value="user3">Николай Смирнов</SelectItem>
                      <SelectItem value="user4">Елена Козлова</SelectItem>
                      <SelectItem value="user5">Дмитрий Соколов</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <Label>Диапазон дат</Label>
                  <div className="flex space-x-2">
                    <div className="flex-1">
                      <Popover open={dateFromOpen} onOpenChange={setDateFromOpen}>
                        <PopoverTrigger asChild>
                          <Button
                            variant="outline"
                            className={cn(
                              "w-full justify-start text-left font-normal",
                              !dateFrom && "text-muted-foreground"
                            )}
                          >
                            <CalendarIcon className="mr-2 h-4 w-4" />
                            {dateFrom ? format(dateFrom, "dd.MM.yyyy") : "С"}
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-auto p-0" align="start">
                          <Calendar
                            mode="single"
                            selected={dateFrom}
                            onSelect={(date) => {
                              setDateFrom(date);
                              setDateFromOpen(false);
                            }}
                            initialFocus
                            className={cn("p-3 pointer-events-auto")}
                          />
                        </PopoverContent>
                      </Popover>
                    </div>
                    <div className="flex-1">
                      <Popover open={dateToOpen} onOpenChange={setDateToOpen}>
                        <PopoverTrigger asChild>
                          <Button
                            variant="outline"
                            className={cn(
                              "w-full justify-start text-left font-normal",
                              !dateTo && "text-muted-foreground"
                            )}
                          >
                            <CalendarIcon className="mr-2 h-4 w-4" />
                            {dateTo ? format(dateTo, "dd.MM.yyyy") : "По"}
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-auto p-0" align="start">
                          <Calendar
                            mode="single"
                            selected={dateTo}
                            onSelect={(date) => {
                              setDateTo(date);
                              setDateToOpen(false);
                            }}
                            initialFocus
                            className={cn("p-3 pointer-events-auto")}
                          />
                        </PopoverContent>
                      </Popover>
                    </div>
                  </div>
                </div>
                
                <Card>
                  <CardContent className="p-4">
                    <h4 className="text-sm font-medium mb-2 flex items-center">
                      <BookmarkIcon className="h-4 w-4 mr-1" />
                      Сохраненные поиски
                    </h4>
                    <div className="space-y-2">
                      {savedSearches.map((search) => (
                        <div 
                          key={search.id} 
                          className="text-sm p-2 rounded-md hover:bg-accent cursor-pointer"
                          onClick={() => loadSavedSearch(search.id)}
                        >
                          <div className="font-medium">{search.name}</div>
                          <div className="text-xs text-muted-foreground">{search.query}</div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
              
              <SheetFooter className="pt-4 border-t">
                <Button variant="outline" onClick={clearFilters}>
                  Сбросить
                </Button>
                <Button onClick={handleApplyFilters}>
                  Применить фильтры
                </Button>
              </SheetFooter>
            </SheetContent>
          </Sheet>
        </div>
      </div>
      
      <div className="mt-2">
        <div className="flex flex-wrap gap-2">
          {documentType && (
            <Badge variant="outline" className="bg-blue-50">
              Тип: {documentType.toUpperCase()}
              <button className="ml-1 hover:text-destructive" onClick={() => setDocumentType('')}>×</button>
            </Badge>
          )}
          {department && (
            <Badge variant="outline" className="bg-green-50">
              Отдел: {department}
              <button className="ml-1 hover:text-destructive" onClick={() => setDepartment('')}>×</button>
            </Badge>
          )}
          {engineer && (
            <Badge variant="outline" className="bg-purple-50">
              Инженер: {engineer}
              <button className="ml-1 hover:text-destructive" onClick={() => setEngineer('')}>×</button>
            </Badge>
          )}
          {dateFrom && (
            <Badge variant="outline" className="bg-orange-50">
              С: {format(dateFrom, "dd.MM.yyyy")}
              <button className="ml-1 hover:text-destructive" onClick={() => setDateFrom(undefined)}>×</button>
            </Badge>
          )}
          {dateTo && (
            <Badge variant="outline" className="bg-orange-50">
              По: {format(dateTo, "dd.MM.yyyy")}
              <button className="ml-1 hover:text-destructive" onClick={() => setDateTo(undefined)}>×</button>
            </Badge>
          )}
        </div>
      </div>
      
      {searchQuery.length === 0 && (
        <div className="mt-4">
          <h4 className="text-sm font-medium mb-2 text-muted-foreground">Подсказки для поиска:</h4>
          <div className="flex flex-wrap gap-2">
            {getSuggestedQueries().map((query, index) => (
              <Badge 
                key={index}
                variant="outline" 
                className="cursor-pointer hover:bg-accent"
                onClick={() => setSearchQuery(query)}
              >
                {query}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
