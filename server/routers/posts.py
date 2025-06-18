import logging
import shutil
import uuid
from pathlib import Path
from typing import List, Annotated, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
    Query,
)
from sqlalchemy.orm import Session, selectinload
from PIL import Image

from database import database, models, schemas
from server.utils import security

logger = logging.getLogger("KindergartenApp.routers.posts")
router = APIRouter()
get_db = database.get_db


UPLOAD_DIR_POSTS = Path("uploads/post_media")
UPLOAD_DIR_POSTS.mkdir(parents=True, exist_ok=True)

THUMBNAIL_SIZE = (300, 300)
MAX_IMAGE_SIZE_MB = 5
ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"]

# --- Эндпоинты для Постов ---


@router.post(
    "/",
    response_model=schemas.PostRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(security.require_admin_role)],
)
async def create_post_with_media(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(security.get_current_active_user)],
    title: Optional[str] = Form(None),
    text_content: str = Form(...),
    is_pinned: bool = Form(False),
    image_file: Optional[UploadFile] = File(None),
):
    """
    Создает новый пост с возможностью загрузки одного изображения.
    """
    logger.info(
        f"User '{current_user.username}' attempting to create a post with media."
    )

    db_post = models.Post(
        title=title,
        text_content=text_content,
        is_pinned=is_pinned,
        author_id=current_user.id,
    )

    saved_media_record = None
    if image_file:
        if image_file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported image type: {image_file.content_type}. Allowed: {ALLOWED_IMAGE_TYPES}",
            )

        if image_file.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Image size exceeds {MAX_IMAGE_SIZE_MB}MB limit.",
            )

        try:
            # Генерируем уникальное имя файла и пути
            file_extension = (
                Path(image_file.filename).suffix.lower()
                if image_file.filename
                else ".jpg"
            )
            if not file_extension:
                file_extension = ".jpg"

            unique_id = uuid.uuid4()
            base_filename = f"{unique_id}{file_extension}"
            thumbnail_filename = f"{unique_id}_thumb{file_extension}"

            file_location = UPLOAD_DIR_POSTS / base_filename
            thumbnail_location = UPLOAD_DIR_POSTS / thumbnail_filename

            # Сохраняем оригинальный (или обработанный) файл
            with open(file_location, "wb+") as file_object:
                shutil.copyfileobj(image_file.file, file_object)

            # Обработка изображения: ресайз и создание превью
            img = Image.open(file_location)

            # Создаем превью
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            img.save(thumbnail_location)

            logger.info(
                f"Image saved to {file_location}, thumbnail to {thumbnail_location}"
            )

            # Создаем запись Media в БД

            saved_media_record = models.Media(
                file_path=str(Path(base_filename)),
                thumbnail_path=str(Path(thumbnail_filename)),
                original_filename=(
                    str(image_file.filename)
                    if image_file.filename
                    else "uploaded_image"
                ),
                mime_type=str(image_file.content_type),
                file_type=models.MediaType.PHOTO,
                uploaded_by_id=current_user.id,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing uploaded image: {e}", exc_info=True)

            if file_location.exists():
                file_location.unlink(missing_ok=True)
            if thumbnail_location.exists():
                thumbnail_location.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process uploaded image.",
            )
        finally:
            image_file.file.close()

    try:
        db.add(db_post)
        db.commit()
        db.refresh(db_post)

        if saved_media_record:
            saved_media_record.post_id = db_post.id
            db.add(saved_media_record)
            db.commit()
            db.refresh(saved_media_record)

            db.refresh(db_post, ["media_files"])
            if db_post.author_id:
                db.refresh(db_post, ["author"])

        logger.info(
            f"Post id={db_post.id} titled '{db_post.title}' created by user '{current_user.username}'."
        )
        return db_post
    except Exception as e:
        db.rollback()
        logger.error(f"Database error creating post with media: {e}", exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create post due to a database error.",
        )


@router.get("/", response_model=List[schemas.PostRead])
async def read_posts(
    db: Annotated[Session, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    pinned_only: Optional[bool] = Query(None, description="Show only pinned posts"),
):
    """
    Получает список постов с пагинацией и возможностью фильтрации.
    Доступно всем аутентифицированным пользователям.
    """
    query = db.query(models.Post).options(
        selectinload(models.Post.media_files), selectinload(models.Post.author)
    )

    if pinned_only is True:
        query = query.filter(models.Post.is_pinned == True)
    elif pinned_only is False:
        query = query.filter(models.Post.is_pinned == False)

    posts = (
        query.order_by(models.Post.is_pinned.desc(), models.Post.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return posts


@router.get("/{post_id}", response_model=schemas.PostRead)
async def read_post(post_id: int, db: Annotated[Session, Depends(get_db)]):
    """
    Получает один пост по его ID.
    Доступно всем аутентифицированным пользователям.
    """
    db_post = (
        db.query(models.Post)
        .options(
            selectinload(models.Post.media_files), selectinload(models.Post.author)
        )
        .filter(models.Post.id == post_id)
        .first()
    )

    if db_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    return db_post


@router.put(
    "/{post_id}",
    response_model=schemas.PostRead,
    dependencies=[Depends(security.require_admin_role)],
)
async def update_post_text_data(
    post_id: int,
    post_in: schemas.PostUpdate,  #
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(security.get_current_active_user)],
):
    """
    Обновляет текстовые данные и флаги существующего поста (title, text_content, is_pinned).
    Изображения управляются через отдельные эндпоинты.
    """
    logger.info(
        f"User '{current_user.username}' updating text data for post id={post_id}."
    )

    db_post = (
        db.query(models.Post)
        .options(selectinload(models.Post.media_files))
        .filter(models.Post.id == post_id)
        .first()
    )

    if db_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    update_data = post_in.model_dump(exclude_unset=True)
    if not update_data:
        logger.info(
            f"No data provided to update post {post_id}. Returning current state."
        )
        return db_post

    for key, value in update_data.items():
        setattr(db_post, key, value)

    try:
        db.add(db_post)
        db.commit()
        db.refresh(db_post)
        db.refresh(db_post, ["media_files"])
        if db_post.author_id:
            db.refresh(db_post, ["author"])
        logger.info(
            f"Post id={db_post.id} text data updated by user '{current_user.username}'."
        )
        return db_post
    except Exception as e:
        db.rollback()
        logger.error(
            f"Database error updating post text data {post_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update post text data due to a database error.",
        )


@router.post(
    "/{post_id}/image",
    response_model=schemas.PostRead,
    dependencies=[Depends(security.require_admin_role)],
)
async def upload_post_image(
    post_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(security.get_current_active_user)],
    image_file: UploadFile = File(...),
):
    """
    Загружает или заменяет изображение для существующего поста.
    Если у поста уже есть изображение, старое будет удалено.
    """
    logger.info(
        f"User '{current_user.username}' uploading image for post id={post_id}."
    )

    db_post = (
        db.query(models.Post)
        .options(selectinload(models.Post.media_files))
        .filter(models.Post.id == post_id)
        .first()
    )
    if db_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    if db_post.media_files:
        current_media_record = db_post.media_files[0]
        logger.info(
            f"Removing existing media (id={current_media_record.id}) for post {post_id} before uploading new one."
        )
        old_file_path = UPLOAD_DIR_POSTS / current_media_record.file_path
        old_thumb_path = (
            UPLOAD_DIR_POSTS / current_media_record.thumbnail_path
            if current_media_record.thumbnail_path
            else None
        )
        try:
            if old_file_path.exists():
                old_file_path.unlink()
            if old_thumb_path and old_thumb_path.exists():
                old_thumb_path.unlink()
        except Exception as e_del_file:
            logger.error(
                f"Error deleting old media files from disk for post {post_id}: {e_del_file}"
            )
        db.delete(current_media_record)

    # Обработка нового файла (аналогично create_post_with_media)
    if image_file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type: {image_file.content_type}. Allowed: {ALLOWED_IMAGE_TYPES}",
        )
    if image_file.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image size exceeds {MAX_IMAGE_SIZE_MB}MB limit.",
        )

    file_location = None
    thumbnail_location = None
    try:
        file_extension = (
            Path(image_file.filename).suffix.lower() if image_file.filename else ".jpg"
        )
        if not file_extension:
            file_extension = ".jpg"
        unique_id = uuid.uuid4()
        base_filename = f"{unique_id}{file_extension}"
        thumbnail_filename = f"{unique_id}_thumb{file_extension}"
        file_location = UPLOAD_DIR_POSTS / base_filename
        thumbnail_location = UPLOAD_DIR_POSTS / thumbnail_filename

        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(image_file.file, file_object)

        img = Image.open(file_location)
        img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        img.save(thumbnail_location)

        new_media_record = models.Media(
            post_id=db_post.id,
            file_path=str(Path(base_filename)),
            thumbnail_path=str(Path(thumbnail_filename)),
            original_filename=(
                str(image_file.filename) if image_file.filename else "uploaded_image"
            ),
            mime_type=str(image_file.content_type),
            file_type=models.MediaType.PHOTO,
            uploaded_by_id=current_user.id,
        )
        db.add(new_media_record)
        logger.info(f"New image {base_filename} associated with post {post_id}.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error processing uploaded image for post {post_id}: {e}", exc_info=True
        )
        if file_location and file_location.exists():
            file_location.unlink(missing_ok=True)
        if thumbnail_location and thumbnail_location.exists():
            thumbnail_location.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process uploaded image.",
        )
    finally:
        image_file.file.close()

    try:
        db.commit()
        db.refresh(db_post)
        db.refresh(db_post, ["media_files"])
        if db_post.author_id:
            db.refresh(db_post, ["author"])
        return db_post
    except Exception as e:
        db.rollback()
        logger.error(
            f"Database error after uploading image for post {post_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error after image upload.",
        )


@router.delete(
    "/{post_id}/image",
    response_model=schemas.PostRead,
    dependencies=[Depends(security.require_admin_role)],
)
async def delete_post_image(
    post_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(security.get_current_active_user)],
):
    """
    Удаляет изображение, связанное с постом (если оно есть).
    """
    logger.info(
        f"User '{current_user.username}' attempting to delete image for post id={post_id}."
    )

    db_post = (
        db.query(models.Post)
        .options(selectinload(models.Post.media_files))
        .filter(models.Post.id == post_id)
        .first()
    )
    if db_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    if not db_post.media_files:
        logger.info(f"No image to delete for post {post_id}.")
        return db_post

    current_media_record = db_post.media_files[0]
    logger.info(f"Deleting media (id={current_media_record.id}) for post {post_id}.")

    old_file_path = UPLOAD_DIR_POSTS / current_media_record.file_path
    old_thumb_path = (
        UPLOAD_DIR_POSTS / current_media_record.thumbnail_path
        if current_media_record.thumbnail_path
        else None
    )
    try:
        if old_file_path.exists():
            old_file_path.unlink()
        if old_thumb_path and old_thumb_path.exists():
            old_thumb_path.unlink()
        logger.info(
            f"Deleted image files from disk for media id {current_media_record.id}"
        )
    except Exception as e_del_file:
        logger.error(
            f"Error deleting image files from disk for post {post_id}: {e_del_file}"
        )

    try:
        db.delete(current_media_record)
        db.commit()
        db.refresh(db_post)
        db.refresh(db_post, ["media_files"])
        if db_post.author_id:
            db.refresh(db_post, ["author"])
        logger.info(f"Image for post id={post_id} deleted successfully.")
        return db_post
    except Exception as e:
        db.rollback()
        logger.error(
            f"Database error deleting media for post {post_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while deleting image.",
        )


@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(security.require_admin_role)],
)
async def delete_post(
    post_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(security.get_current_active_user)],
):
    """
    Удаляет пост и все связанные с ним медиафайлы (как из БД, так и с диска).
    """
    logger.info(
        f"User '{current_user.username}' attempting to delete post id={post_id}."
    )

    db_post = (
        db.query(models.Post)
        .options(selectinload(models.Post.media_files))
        .filter(models.Post.id == post_id)
        .first()
    )

    if db_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    post_title_for_log = db_post.title

    # --- Удаление файлов с диска ---
    if db_post.media_files:
        logger.info(
            f"Post {post_id} has {len(db_post.media_files)} media file(s) to delete from disk."
        )
        for media_record in db_post.media_files:
            paths_to_delete = []
            if media_record.file_path:
                paths_to_delete.append(UPLOAD_DIR_POSTS / media_record.file_path)
            if media_record.thumbnail_path:
                paths_to_delete.append(UPLOAD_DIR_POSTS / media_record.thumbnail_path)

            for file_on_disk in paths_to_delete:
                try:
                    if (
                        file_on_disk.exists() and file_on_disk.is_file()
                    ):  # Проверяем, что это файл
                        file_on_disk.unlink()
                        logger.info(
                            f"Successfully deleted file from disk: {file_on_disk}"
                        )
                    elif (
                        file_on_disk.exists()
                    ):  # Если это не файл (например, папка с таким именем случайно)
                        logger.warning(
                            f"Path exists but is not a file, skipping deletion: {file_on_disk}"
                        )
                    else:
                        logger.warning(
                            f"File not found on disk, skipping deletion: {file_on_disk}"
                        )
                except Exception as e_file_del:
                    # Логируем ошибку, но продолжаем удаление записи из БД и остальных файлов
                    logger.error(
                        f"Error deleting file {file_on_disk} from disk for media_id {media_record.id}: {e_file_del}"
                    )
    else:
        logger.info(f"Post {post_id} has no media files to delete from disk.")

    # --- Удаление из БД ---

    try:
        db.delete(db_post)
        db.commit()
        logger.info(
            f"Post id={post_id} (title: '{post_title_for_log}') and its DB media records deleted by user '{current_user.username}'."
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Database error deleting post {post_id}: {e}", exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete post from database after attempting to clean up files.",
        )
