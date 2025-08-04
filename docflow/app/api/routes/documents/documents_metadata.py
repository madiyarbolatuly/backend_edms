from typing import Any, Dict, List, Union
from uuid import UUID

from fastapi import APIRouter, status, Body, Depends, Query, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pathlib import Path
from fastapi import UploadFile, File
from app.schemas.documents.documents_metadata import DocumentMetadataCreate, DocumentMetadataRead, FolderCreate

from app.api.dependencies.repositories import get_repository
from app.api.dependencies.auth_utils import get_current_user
from app.core.config import settings
from app.core.exceptions import http_404
from app.db.crud import get_user_by_id
from app.db.repositories.auth.auth import AuthRepository
from app.db.repositories.documents.documents_metadata import MetadataRepository
from app.schemas.auth.bands import TokenData
from app.schemas.documents.bands import DocumentMetadataPatch
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.database import get_async_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v2/u/login")

router = APIRouter(tags=["Document MetaData"])


@router.post(
    "/upload",
    response_model=DocumentMetadataRead,
    status_code=status.HTTP_201_CREATED,
    name="upload_documents_metadata",
)
async def upload_document_metadata(
    document_upload: DocumentMetadataCreate = Body(...),
    repository: MetadataRepository = Depends(
        get_repository(MetadataRepository)
    ),
    user: TokenData = Depends(get_current_user),    
) -> DocumentMetadataRead:
    """
    Uploads document metadata.

    Args:
        document_upload (DocumentMetadataCreate): The document metadata to be uploaded.
        repository (MetadataRepository): The repository for managing document metadata.
        user (TokenData): The token data of the authenticated user.

    Returns:
        DocumentMetadataRead: The uploaded document metadata.
    """

    document_upload.owner_id = user.id
    return await repository.upload(document_upload=document_upload)


@router.get(
    "",
    response_model=Dict[str, Union[List[DocumentMetadataRead], Any]],
    status_code=status.HTTP_200_OK,
    name="get_documents_metadata",
)
async def get_documents_metadata(
    limit: int = Query(default=10, lt=100),
    offset: int = Query(default=0),
    repository: MetadataRepository = Depends(
        get_repository(MetadataRepository)
    ),
    user: TokenData = Depends(get_current_user),
) -> Dict[str, Union[List[DocumentMetadataRead], Any]]:
    """
    Retrieves a list of document metadata.

    Args:
        limit (int): The maximum number of documents to retrieve. Defaults to 10.
        offset (int): The number of documents to skip. Defaults to 0.
        repository (MetadataRepository): The repository for managing document metadata.
        user (TokenData): The token data of the authenticated user.

    Returns:
        Dict[str, Union[List[DocumentMetadataRead], Any]]: A dictionary containing the list of document metadata.
    """

    return await repository.doc_list(limit=limit, offset=offset, owner=user)


@router.get(
    "/{document}/detail",
    response_model=None,
    status_code=status.HTTP_200_OK,
    name="get_document-metadata",
)
async def get_document_metadata(
    document: Union[str, UUID],
    repository: MetadataRepository = Depends(
        get_repository(MetadataRepository)
    ),
    user: TokenData = Depends(get_current_user),
) -> Union[DocumentMetadataRead, HTTPException]:
    """ Retrieves the metadata of a specific document.

    Args:
        document (Union[str, UUID]): The ID or name of the document.
        repository (MetadataRepository): The repository for managing document metadata.
        user (TokenData): The token data of the authenticated user.

    Returns:
        Union[DocumentMetadataRead, HTTPException]: The document metadata if found, otherwise an HTTPException.
    """

    return await repository.get(document=document, owner=user)


@router.put(
    "/{document}",
    response_model=None,
    status_code=status.HTTP_200_OK,
    name="update_doc_metadata_details",
)
async def update_doc_metadata_details(
    document: Union[str, UUID],
    document_patch: DocumentMetadataPatch = Body(...),
    repository: MetadataRepository = Depends(
        get_repository(MetadataRepository)
    ),
    user_repository: AuthRepository = Depends(get_repository(AuthRepository)),
    user: TokenData = Depends(get_current_user),
) -> Union[DocumentMetadataRead, HTTPException]:
    """
    Updates the details of a document's metadata.

    Args:
        document (Union[str, UUID]): The ID or name of the document.
        document_patch (DocumentMetadataPatch): The document metadata patch containing the updated details.
        repository (MetadataRepository): The repository for managing document metadata.
        user_repository (AuthRepository): The repository for managing user authentication.
        user (TokenData): The token data of the authenticated user.

    Returns:
        Union[DocumentMetadataRead, HTTPException]: The updated document metadata if successful,
        otherwise an HTTPException.

    Raises:
        HTTP_404: If no document with the specified ID or name is found.
    """

    try:
        await repository.get(document=document, owner=user)
    except Exception as e:
        raise http_404(msg=f"No Document with: {document}") from e

    return await repository.patch(
        document=document,
        document_patch=document_patch,
        owner=user,
        user_repo=user_repository,
        is_owner=True,
    )


@router.delete(
    "/{document}",
    status_code=status.HTTP_204_NO_CONTENT,
    name="delete_document_metadata",
)
async def delete_document_metadata(
    document: Union[str, UUID],
    repository: MetadataRepository = Depends(
        get_repository(MetadataRepository)
    ),
    user: TokenData = Depends(get_current_user),
) -> None:
    """
    Deletes the metadata of a document and moves it toa the bin.

    Args:
        document (Union[str, UUID]): The identifier of the document to delete.
        repository (MetadataRepository): The repository for accessing document metadata.
            Defaults to the result of the `get_repository` function with `MetadataRepository` as the argument.
        user (TokenData): The token data of the current user. Defaults to the result of the `get_current_user` function.

    Returns:
        None (204_NO_CONTENT)

    Raises:
        HTTP_404: If no document with the specified identifier is found.
    """

    try:
        await repository.get(document=document, owner=user)
    except Exception as e:
        raise http_404(msg=f"No document with the detail: {document}.") from e

    return await repository.delete(document=document, owner=user)


# Archiving


@router.post(
    "/archive/{file_name}",
    response_model=DocumentMetadataRead,
    status_code=status.HTTP_200_OK,
    name="archive_a_document",
)
async def archive_doc(
    file_name: str,
    repo: MetadataRepository = Depends(get_repository(MetadataRepository)),
    user: TokenData = Depends(get_current_user),
) -> DocumentMetadataRead:
    """
    Archive a document.

    Args:
        file_name (str): The name of the file to be archived.
        repository (MetadataRepository): The repository for document metadata.
        user (TokenData): The user token data.

    Returns:
        DocumentMetadataRead: The archived document metadata.

    """

    return await repo.archive(document=file_name, user=user)


@router.get(
    "/archive/list",
    response_model=None,
    status_code=status.HTTP_200_OK,
    name="archived_doc_list",
)

async def list_archived(
    repo: MetadataRepository = Depends(get_repository(MetadataRepository)),
    user: TokenData = Depends(get_current_user),
) -> Dict[str, List[str] | int]:
    """
    Get the list of archived documents.

    Args:
        repository (MetadataRepository): The repository for document metadata.
        user (TokenData): The user token data.

    Returns:
        Dict[str, List[str] | int]: A dictionary containing the list of archived documents.

    """

    return await repo.archive_list(user=user)


@router.post(
    "/un-archive/{file_name}",
    response_model=DocumentMetadataRead,
    status_code=status.HTTP_200_OK,
    name="remove_doc_from_archive",
)
async def unarchive_doc(
    file_name: str,
    repo: MetadataRepository = Depends(get_repository(MetadataRepository)),
    user: TokenData = Depends(get_current_user),
) -> DocumentMetadataRead:
    """
    Un-archive a document.

    Args:
        file (str): The name of the file to be un-archived.
        repository (MetadataRepository): The repository for document metadata.
        user (TokenData): The user token data.

    Returns:
        DocumentMetadataRead: The un-archived document metadata.

    """

    return await repo.un_archive(document=file_name, user=user)


@router.get("/v2/u/me", tags=["User"])
async def read_users_me(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_async_session),   # ← берём сессию
):
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,                   
            algorithms=[settings.algorithm],
        )
        user_id: str | None = payload.get("id")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user = await get_user_by_id(session, user_id)         
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": user.created_at,
    }


@router.post(
    "/v2/metadata/upload",
    response_model=DocumentMetadataRead,
    status_code=status.HTTP_201_CREATED,
    name="create_folder"
)
async def create_folder(
    folder: FolderCreate,
    repository: MetadataRepository = Depends(get_repository(MetadataRepository)),
    user: TokenData = Depends(get_current_user)
) -> DocumentMetadataRead:
    """
    Create a new folder entry. Does not upload any file content.
    """
    metadata = DocumentMetadataCreate(**folder.dict())
    metadata.owner_id = user.id
    metadata.type = "folder"
    # Optional: Validate parent exists and is a folder
    if metadata.parent_id:
        parent = await repository.get(document=metadata.parent_id, owner=user)
        if not parent or getattr(parent, "type", None) != "folder":
            raise HTTPException(status_code=400, detail="Parent must be a folder.")
    return await repository.upload(document_upload=metadata)

@router.patch("/{document_id}", response_model=DocumentMetadataRead, status_code=status.HTTP_200_OK, name="patch_document_metadata")
async def patch_document_metadata(
    document_id: Union[str, UUID],
    document_patch: DocumentMetadataPatch = Body(...),
    repository: MetadataRepository = Depends(get_repository(MetadataRepository)),
    user_repository: AuthRepository = Depends(get_repository(AuthRepository)),
    user: TokenData = Depends(get_current_user),
) -> DocumentMetadataRead:
    try:
        await repository.get(document=document_id, owner=user)
    except Exception as e:
        raise http_404(msg=f"No Document with: {document_id}") from e
    return await repository.patch(
        document=document_id,
        document_patch=document_patch,
        owner=user,
        user_repo=user_repository,
        is_owner=True,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: UUID, repository: MetadataRepository = Depends(get_repository(MetadataRepository))):
    if await repository.is_document_archived(document_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete archived document.")
    # ...existing delete logic...


@router.patch("/{document_id}")
async def edit_document(document_id: UUID, repository: MetadataRepository = Depends(get_repository(MetadataRepository))):
    if await repository.is_document_archived(document_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit archived document.")
    # ...existing edit logic...


@router.put("/{document_id}/rename")
async def rename_document(document_id: UUID, repository: MetadataRepository = Depends(get_repository(MetadataRepository))):
    if await repository.is_document_archived(document_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot rename archived document.")
    # ...existing rename logic...
    

@router.put("/{document_name}/star")
async def toggle_star(document_name: str, repository: MetadataRepository = Depends(get_repository(MetadataRepository))):
    doc = await repository.get_by_name(document_name)
    if not doc:
        raise HTTPException(404, detail="Document not found")
    await repository.toggle_favourited(doc.id)
    return {"message": "favourited status toggled successfully."}

