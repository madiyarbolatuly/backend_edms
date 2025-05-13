
export type DocumentType = 'pdf' | 'doc' | 'docx' | 'xlsx' | 'xls' | 'ppt' | 'pptx' | 'jpg' | 'jpeg' | 'png' | 'txt' | 'folder' | 'image';

export interface Document {
  id: string;
  name: string;
  type: DocumentType;
  size?: string; // Make size optional since folders don't always have a size
  modified: string;
  owner: string;
  category: string;
  thumbnail?: string;
  favorited?: boolean;
  path?: string;
  dueDate?: string;
  engineer?: string;
  linkedAssets?: string[];
  shared?: boolean;  // Added back the shared property
}

// Add the missing Version interface
export interface Version {
  id: string;
  versionNumber: number;
  createdAt: string;
  createdBy: string;
  comments: string;
  version?: string;      // For backward compatibility
  modified?: string;     // For backward compatibility
  modifiedBy?: string;   // For backward compatibility
  size?: string;         // For backward compatibility
  comment?: string;      // For backward compatibility
}

// Add back CategoryType which is used in several components
export type CategoryType = 
  | 'all' 
  | 'recent' 
  | 'shared' 
  | 'favorites' 
  | 'trash' 
  | 'managers' 
  | 'development' 
  | 'procurement' 
  | 'electrical' 
  | 'weakening' 
  | 'interface' 
  | 'pse'
  | string;

// Add back ActivityAction which is used in DocumentDetails.tsx
export type ActivityAction = 
  | "viewed" 
  | "modified" 
  | "commented" 
  | "uploaded" 
  | "deleted" 
  | "restored" 
  | "downloaded" 
  | "shared";

// Add back MultipleSelectionActions which is used in DocumentGrid.tsx
export interface MultipleSelectionActions {
  selectedIds: string[];
  onSelectAll?: () => void;
  onClearSelection?: () => void;
  onDeleteSelected?: () => void;
  onRestoreSelected?: () => void;
  onDownloadSelected?: () => void;
  onMoveSelected?: () => void;
  onShareSelected?: () => void;
}
