
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FileDiff, FileSearch } from 'lucide-react';

interface DocumentComparisonProps {
  documentId?: string;
}

interface DiffLine {
  type: 'added' | 'removed' | 'unchanged';
  content: string;
}

// Mock data for the diff view
const MOCK_DIFF: DiffLine[] = [
  { type: 'unchanged', content: '# Технический отчет' },
  { type: 'unchanged', content: '' },
  { type: 'unchanged', content: '## Введение' },
  { type: 'unchanged', content: 'Данный документ содержит технические спецификации для проекта.' },
  { type: 'removed', content: 'Версия оборудования: v2.5' },
  { type: 'added', content: 'Версия оборудования: v3.0' },
  { type: 'unchanged', content: '' },
  { type: 'unchanged', content: '## Технические параметры' },
  { type: 'unchanged', content: '' },
  { type: 'unchanged', content: '### Основные характеристики' },
  { type: 'unchanged', content: '- Мощность: 750 кВт' },
  { type: 'removed', content: '- Напряжение: 380В' },
  { type: 'added', content: '- Напряжение: 400В' },
  { type: 'unchanged', content: '- Частота: 50 Гц' },
  { type: 'unchanged', content: '' },
  { type: 'unchanged', content: '### Условия эксплуатации' },
  { type: 'removed', content: '- Температура: от -20°C до +40°C' },
  { type: 'added', content: '- Температура: от -30°C до +50°C' },
  { type: 'added', content: '- Влажность: до 95%' },
  { type: 'unchanged', content: '- Высота над уровнем моря: до 1000м' },
];

export function DocumentComparison({ documentId }: DocumentComparisonProps) {
  const [oldVersion, setOldVersion] = React.useState('v1.1');
  const [newVersion, setNewVersion] = React.useState('v1.2');
  
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center">
          <FileDiff className="h-5 w-5 mr-2" />
          Сравнение версий
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex justify-between items-center mb-4 gap-4">
          <div className="flex-1">
            <label className="text-sm font-medium mb-1 block">Старая версия</label>
            <Select value={oldVersion} onValueChange={setOldVersion}>
              <SelectTrigger>
                <SelectValue placeholder="Выберите версию" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="v1.0">Версия 1.0</SelectItem>
                <SelectItem value="v1.1">Версия 1.1</SelectItem>
              </SelectContent>
            </Select>
          </div>
          
          <div className="flex-1">
            <label className="text-sm font-medium mb-1 block">Новая версия</label>
            <Select value={newVersion} onValueChange={setNewVersion}>
              <SelectTrigger>
                <SelectValue placeholder="Выберите версию" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="v1.1">Версия 1.1</SelectItem>
                <SelectItem value="v1.2">Версия 1.2</SelectItem>
                <SelectItem value="v2.0-draft1">Версия 2.0 (черновик 1)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        
        <Tabs defaultValue="text">
          <TabsList className="mb-4">
            <TabsTrigger value="text">Текстовое сравнение</TabsTrigger>
            <TabsTrigger value="visual">Визуальное сравнение</TabsTrigger>
          </TabsList>
          
          <TabsContent value="text">
            <div className="border rounded-md overflow-hidden">
              <div className="bg-muted p-2 text-sm font-medium">
                Изменения от {oldVersion} к {newVersion}
              </div>
              <div className="p-4 bg-card text-sm font-mono whitespace-pre-wrap">
                {MOCK_DIFF.map((line, index) => (
                  <div 
                    key={index} 
                    className={`${
                      line.type === 'added' 
                        ? 'bg-green-50 text-green-900 border-l-4 border-green-500' 
                        : line.type === 'removed' 
                        ? 'bg-red-50 text-red-900 border-l-4 border-red-500' 
                        : ''
                    } py-0.5 px-2 -mx-2`}
                  >
                    <span className="inline-block w-5 text-muted-foreground">
                      {line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' '}
                    </span>
                    {line.content}
                  </div>
                ))}
              </div>
            </div>
          </TabsContent>
          
          <TabsContent value="visual">
            <div className="flex justify-center items-center p-8 border rounded-md bg-muted/20">
              <div className="text-center text-muted-foreground">
                <FileSearch className="h-12 w-12 mx-auto mb-2 text-muted-foreground/70" />
                <p>Визуальное сравнение недоступно для данного типа документа</p>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
