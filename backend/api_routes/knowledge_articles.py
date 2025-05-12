from typing import List
from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import session

from ..services import (
    get_current_user_dep,
    check_user_permission,
    Actions,
    ArticleService,
)
from ..schemas import (
    StandardResponse,
    ArticleCreateSchema,
    ArticleSchema,
    ArticleUpdateSchema,
)
from ..models import Users
from ..utils import session

articlesRouter = APIRouter(prefix="/knowledge-articles", tags=["Knowledge Articles"])


@articlesRouter.post("/", response_model=StandardResponse[ArticleSchema])
async def create_article(
    article: ArticleCreateSchema,
    db=Depends(session.get_db),
    current_user: Users = Depends(get_current_user_dep),
):
    """Creates a new article resource"""
    permitted = await check_user_permission(
        user_id=str(current_user.id),
        action=Actions.CREATE.value,
        tenant_id=str(current_user.active_workspace),
    )
    if not permitted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have the right permissions",
        )

    result = ArticleService.create_article(db=db, article=article)

    new_article = ArticleSchema.model_validate(result)

    return JSONResponse(
        {"data": new_article.model_dump(), "status": "success"},
        status_code=status.HTTP_201_CREATED,
    )


@articlesRouter.get("/", response_model=StandardResponse[List[ArticleSchema]])
async def fetch_tenant_articles(
    db=Depends(session.get_db), current_user: Users = Depends(get_current_user_dep)
):
    """Fetch all knowledge resources in a tenant"""
    permitted = await check_user_permission(
        user_id=str(current_user.id),
        action=Actions.READ.value,
        tenant_id=str(current_user.active_workspace),
    )
    if not permitted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to view this resources",
        )
    data = ArticleService.retrieve_tenant_articles(
        db=db, tenant_id=str(current_user.active_workspace)
    )

    articles = [ArticleSchema.model_validate(article) for article in data]
    article_arr = [article.model_dump() for article in articles]

    return JSONResponse(
        {"data": article_arr, "status": "success"},
        status_code=status.HTTP_200_OK,
    )


@articlesRouter.get(
    "/{article_id}", response_model=StandardResponse[ArticleCreateSchema]
)
async def fetch_article_by_id(
    article_id: str,
    db=Depends(session.get_db),
    current_user: Users = Depends(get_current_user_dep),
):
    """Fetch knowledge resource by ID"""
    permitted = await check_user_permission(
        user_id=str(
            current_user.id,
        ),
        action=Actions.READ.value,
        tenant_id=str(current_user.active_workspace),
    )
    if not permitted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to view this resource",
        )

    data = ArticleService.get_article_by_id(
        db=db, tenant_id=current_user.active_workspace, article_id=article_id
    )

    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article '{article_id}' not found",
        )

    article = ArticleSchema.model_validate(data)
    return JSONResponse(
        {"data": article.model_dump(), "status": "success"},
        status_code=status.HTTP_200_OK,
    )


@articlesRouter.patch(
    "/{article_id}", response_model=StandardResponse[ArticleCreateSchema]
)
async def update_by_id(
    article_id: str,
    update_obj: ArticleUpdateSchema,
    db=Depends(session.get_db),
    current_user: Users = Depends(get_current_user_dep),
):
    """Fetch knowledge resource by ID"""
    permitted = await check_user_permission(
        user_id=str(current_user.id),
        action=Actions.UPDATE.value,
        tenant_id=str(current_user.active_workspace),
    )
    if not permitted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to update this resources",
        )

    ArticleService.update_article(
        db=db,
        tenant_id=current_user.active_workspace,
        article_id=article_id,
        update_obj=update_obj,
    )
    return JSONResponse(
        {"data": None, "status": "success"},
        status_code=status.HTTP_200_OK,
    )


@articlesRouter.delete(
    "/{article_id}", response_model=StandardResponse[ArticleCreateSchema]
)
async def delete_by_id(
    article_id: str,
    db=Depends(session.get_db),
    current_user: Users = Depends(get_current_user_dep),
):
    """Fetch knowledge resource by ID"""
    permitted = await check_user_permission(
        user_id=str(current_user.id),
        action=Actions.DELETE.value,
        tenant_id=str(current_user.active_workspace),
    )
    if not permitted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to delete this resource",
        )

    ArticleService.delete_article(
        db=db,
        tenant_id=current_user.active_workspace,
        article_id=article_id,
    )

    return JSONResponse(
        {"data": None, "status": "success"},
        status_code=status.HTTP_200_OK,
    )
