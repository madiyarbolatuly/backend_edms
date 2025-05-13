
import React from 'react';
import { Search, Filter } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

interface SearchBarProps {
  query: string;
  setQuery: (query: string) => void;
  placeholder?: string;
  showFilterButton?: boolean;
}

export function SearchBar({ 
  query, 
  setQuery, 
  placeholder = "Искать документы...",
  showFilterButton = true 
}: SearchBarProps) {
  return (
    <div className="flex gap-2 w-full max-w-2xl">
      <div className="relative flex-1">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
        <Input
          type="text"
          placeholder={placeholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-10 w-full"
        />
      </div>
      {showFilterButton && (
        <Button variant="outline" size="icon" className="shrink-0">
          <Filter className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}
