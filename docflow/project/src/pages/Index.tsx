import React, { useState, useEffect } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { DocumentGrid } from '@/components/DocumentGrid';
import { PageHeader } from '@/components/PageHeader';
import { Document, CategoryType } from '@/types/document';
import { useToast } from '@/hooks/use-toast';
import { MetadataSidebar } from '@/components/MetadataSidebar';
import { useRoleBasedDocuments } from '@/hooks/useRoleBasedDocuments';
import { Button } from '@/components/ui/button';
import { FileUploadDialog } from '@/components/FileUploadDialog';
import { useNavigate } from 'react-router-dom';

interface BackendDocument {
  owner_id: string;
  name: string;
  file_path: string;
  created_at: string;
  size: number;
  file_type: string;
  tags: string[] | null;
  categories: string[] | null;
  status: string;
  file_hash: string;
  access_to: string[] | null;
  id: string;
}

const Index = () => {
  const [category, setCategory] = useState<CategoryType>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [showSidebar, setShowSidebar] = useState(false);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [currentPath, setCurrentPath] = useState<Document[]>([]);
  const { toast } = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    const fetchDocuments = async () => {
      try {
        const response = await fetch("http://localhost:8000/v2/metadata?limit=10&offset=0", {
          headers: {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NDcxMTM0NzgsImlkIjoiMDFKVFE4SzZDSDk5WFdSV1FHRzlXUVlaUUgiLCJ1c2VybmFtZSI6InN0cmluZyJ9.8cgLb1wVYrB8dHrwmMaZv1Jv-q7uas33306G_PdaXGM"
          }
        });
        
        if (!response.ok) {
          throw new Error('Failed to fetch documents');
        }

        const data = await response.json();
        console.log(data);

        // Transform backend documents to match our Document interface
        const transformedDocuments: Document[] = data["documents of string"].map((doc: BackendDocument) => ({
          id: doc.id,
          name: decodeURIComponent(doc.name),
          type: doc.file_type.includes('pdf') ? 'pdf' :
                doc.file_type.includes('doc') ? 'doc' :
                doc.file_type.includes('image') ? 'image' : 'pdf',
          size: `${(doc.size / (1024 * 1024)).toFixed(2)} MB`,
          modified: doc.created_at,
          owner: doc.owner_id,
          category: doc.categories?.[0] || 'uncategorized',
          path: doc.file_path
        }));
        

        setDocuments(transformedDocuments);
      } catch (error) {
        console.error('Error fetching documents:', error);
        toast({
          title: "Error",
          description: "Failed to fetch documents",
          variant: "destructive"
        });
      }
    };

    fetchDocuments();
  }, [toast]);

  const handleDocumentClick = (document: Document) => {
    toast({
      title: "Document selected",
      description: `Selected: ${document.name}`,
    });
  };

  const handleFolderOpen = (folder: Document) => {
    toast({
      title: "Opening folder",
      description: `Opening folder: ${folder.name}`,
    });
    setCurrentPath([...currentPath, folder]);
  };

  const handlePreviewFile = (file: Document) => {
    setSelectedDocument(file);
    setShowSidebar(true);
  };

  const handleDocumentSelect = (document: Document) => {
    if (selectedDocumentIds.includes(document.id)) {
      setSelectedDocumentIds(selectedDocumentIds.filter(id => id !== document.id));
      if (selectedDocument?.id === document.id) {
        setSelectedDocument(null);
        setShowSidebar(false);
      }
    } else {
      setSelectedDocumentIds([...selectedDocumentIds, document.id]);
      if (selectedDocumentIds.length === 0) {
        setSelectedDocument(document);
        setShowSidebar(true);
      }
    }
  };

  const handleSelectAll = () => {
    if (selectedDocumentIds.length === documents.length) {
      setSelectedDocumentIds([]);
      setSelectedDocument(null);
      setShowSidebar(false);
    } else {
      setSelectedDocumentIds(documents.map(doc => doc.id));
      if (!selectedDocument && documents.length > 0) {
        setSelectedDocument(documents[0]);
        setShowSidebar(true);
      }
    }
  };

  const handleClearSelection = () => {
    setSelectedDocumentIds([]);
    setSelectedDocument(null);
    setShowSidebar(false);
  };

  const handleDeleteSelected = () => {
    toast({
      title: "Deleting documents",
      description: `Selected ${selectedDocumentIds.length} documents for deletion`,
    });
    setSelectedDocumentIds([]);
    setSelectedDocument(null);
    setShowSidebar(false);
  };

  const handleDownloadSelected = () => {
    toast({
      title: "Downloading documents",
      description: `Selected ${selectedDocumentIds.length} documents for download`,
    });
  };

  const handleShareSelected = () => {
    toast({
      title: "Sharing documents",
      description: `Selected ${selectedDocumentIds.length} documents for sharing`,
    });
  };

  const handleSelectDestination = (destination: 'downloads' | 'new') => {
    toast({
      title: "Folder selected",
      description: destination === 'downloads' ? "Selected Downloads folder" : "Selected New folder",
    });
  };

  const handleCreateFolder = () => {
    toast({
      title: "Creating folder",
      description: "Creating new folder",
    });
  };

  const handleUploadToDestination = () => {
    toast({
      title: "Uploading files",
      description: "Files uploaded to selected folder",
    });
    setShowUploadDialog(false);
  };

  const handleCloseSidebar = () => {
    setSelectedDocument(null);
    setShowSidebar(false);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar activeCategory={category} onCategoryChange={setCategory} />
      
      <main className="flex-1 h-full overflow-hidden flex flex-col">
        <div className="p-6 flex-1 overflow-auto">
          <PageHeader 
            title="All Documents"
            categoryType={category}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            viewMode={viewMode}
            setViewMode={setViewMode}
          />
          
          <div className="mt-4 animate-fade-in">
            <DocumentGrid 
              documents={documents} 
              onDocumentClick={handleDocumentClick}
              viewMode={viewMode}
              selectedDocument={selectedDocument}
              onDocumentSelect={handleDocumentSelect}
              multipleSelection={true}
              selectionActions={{
                selectedIds: selectedDocumentIds,
                onSelectAll: handleSelectAll,
                onClearSelection: handleClearSelection,
                onDeleteSelected: handleDeleteSelected,
                onDownloadSelected: handleDownloadSelected,
                onShareSelected: handleShareSelected
              }}
              onFolderOpen={handleFolderOpen}
              onPreviewFile={handlePreviewFile}
            />
          </div>
        </div>
        
        {showSidebar && (
          <div className="border-t h-1/2 overflow-hidden">
            <MetadataSidebar 
              document={selectedDocument || undefined} 
              onClose={handleCloseSidebar} 
            />
          </div>
        )}
      </main>
      
      <FileUploadDialog
        open={showUploadDialog}
        onOpenChange={setShowUploadDialog}
        onSelectDestination={handleSelectDestination}
        onCreateFolder={handleCreateFolder}
        onUpload={handleUploadToDestination}
      />
    </div>
  );
};

export default Index;