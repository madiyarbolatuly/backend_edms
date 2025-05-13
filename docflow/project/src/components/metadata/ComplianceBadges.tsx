
import React from 'react';
import { Badge } from "@/components/ui/badge";
import { HelpCircle } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

// Mock compliance data
export type ComplianceType = 
  | 'ISO9001' 
  | 'GOST' 
  | 'KAZREG' 
  | 'SAFETY' 
  | 'ENVIRONMENT' 
  | 'QUALITY';

interface ComplianceBadge {
  type: ComplianceType;
  label: string;
  description: string;
  color: string;
}

export const COMPLIANCE_BADGES: Record<ComplianceType, ComplianceBadge> = {
  ISO9001: {
    type: 'ISO9001',
    label: 'ISO 9001',
    description: 'Соответствует стандарту качества ISO 9001',
    color: 'bg-blue-100 text-blue-800 hover:bg-blue-100'
  },
  GOST: {
    type: 'GOST',
    label: 'ГОСТ',
    description: 'Соответствует государственным стандартам',
    color: 'bg-green-100 text-green-800 hover:bg-green-100'
  },
  KAZREG: {
    type: 'KAZREG',
    label: 'KZ',
    description: 'Соответствует нормативам Казахстана',
    color: 'bg-teal-100 text-teal-800 hover:bg-teal-100'
  },
  SAFETY: {
    type: 'SAFETY',
    label: 'Безопасность',
    description: 'Прошел проверку безопасности',
    color: 'bg-red-100 text-red-800 hover:bg-red-100'
  },
  ENVIRONMENT: {
    type: 'ENVIRONMENT',
    label: 'Экология',
    description: 'Соответствует экологическим требованиям',
    color: 'bg-emerald-100 text-emerald-800 hover:bg-emerald-100'
  },
  QUALITY: {
    type: 'QUALITY',
    label: 'Качество',
    description: 'Прошел контроль качества',
    color: 'bg-purple-100 text-purple-800 hover:bg-purple-100'
  }
};

interface ComplianceBadgesProps {
  badges: ComplianceType[];
  showTooltips?: boolean;
}

export function ComplianceBadges({ badges, showTooltips = true }: ComplianceBadgesProps) {
  if (!badges || badges.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {badges.map(badge => {
        const badgeData = COMPLIANCE_BADGES[badge];
        
        if (!badgeData) return null;
        
        const badgeElement = (
          <Badge key={badge} variant="outline" className={badgeData.color}>
            {badgeData.label}
          </Badge>
        );
        
        if (!showTooltips) return badgeElement;
        
        return (
          <TooltipProvider key={badge}>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="inline-flex">
                  {badgeElement}
                </div>
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <p>{badgeData.description}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        );
      })}
    </div>
  );
}
