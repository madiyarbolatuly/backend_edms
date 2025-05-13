
import React, { useState } from "react";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { BarChart3, Users } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

interface RoleSelectorProps {
  roles: any[];
  selectedRole: string;
  onRoleChange: (roleId: string) => void;
  isLoading?: boolean;
}

export function RoleSelector({ roles, selectedRole, onRoleChange, isLoading = false }: RoleSelectorProps) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        <Label className="text-muted-foreground">Выбор роли пользователя</Label>
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }
  
  if (!roles || roles.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <Label className="text-muted-foreground flex items-center">
        <Users className="h-4 w-4 mr-2" />
        Выбор роли пользователя
      </Label>
      <Select value={selectedRole} onValueChange={onRoleChange}>
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Выберите роль" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {roles.map((role) => (
              <SelectItem key={role.id || role.name} value={role.id || role.name}>
                <div className="flex items-center">
                  <BarChart3 className="h-4 w-4 mr-2 text-muted-foreground" />
                  {role.name || role.id}
                </div>
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  );
}
