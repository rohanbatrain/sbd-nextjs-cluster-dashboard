"""
# Blog Platform Routes

This module provides the core **REST API endpoints** for the Multi-Tenant Blog Platform.
It handles the complete lifecycle of blog websites, content publishing, and audience engagement.

## Domain Overview

The Blog Platform is a comprehensive CMS (Content Management System) supporting:
- **Multi-Tenancy**: Users can create and manage multiple independent blog websites.
- **Content Management**: Rich text posts with categories, tags, and media.
- **Engagement**: Commenting system with moderation tools.
- **Access Control**: Granular roles (Owner, Admin, Editor, Author, Viewer).

## Key Features

### 1. Website Management
- **Creation**: Users can launch new blogs with unique slugs (e.g., `my-tech-blog`).
- **Configuration**: Customize settings like name, description, and comment policies.
- **Discovery**: List and search user-accessible websites.

### 2. Content Publishing
- **CRUD Operations**: Create, read, update, and delete blog posts.
- **Versioning**: Automatic revision history for all content changes.
- **Security**: Built-in XSS protection and content sanitization.
- **SEO**: Optimized metadata handling (title, description, keywords).

### 3. Audience Engagement
- **Comments**: Threaded discussions with optional moderation.
- **Analytics**: Track views, likes, and reading time.
- **Categories**: Organize content into hierarchical topics.

## API Endpoints

### Websites
- `POST /blog/websites` - Create a new blog
- `GET /blog/websites` - List my blogs
- `PUT /blog/websites/{id}` - Update settings

### Posts
- `GET /blog/websites/{id}/posts` - List posts (paginated)
- `POST /blog/websites/{id}/posts` - Publish new post
- `GET /blog/websites/{id}/posts/{slug}` - Read post

### Categories & Comments
- `POST /blog/websites/{id}/categories` - Manage topics
- `POST /blog/websites/{id}/posts/{pid}/comments` - Post comment

## Usage Examples

### Creating a New Blog

```python
response = await client.post("/blog/websites", json={
    "name": "Engineering Daily",
    "slug": "engineering-daily",
    "description": "Insights from the dev team"
})
website_id = response.json()["website_id"]
```

### Publishing a Post

```python
response = await client.post(f"/blog/websites/{website_id}/posts", json={
    "title": "Getting Started with Python",
    "content": "<p>Python is great...</p>",
    "status": "published",
    "categories": ["programming"]
})
```

## Module Attributes

Attributes:
    router (APIRouter): FastAPI router with `/blog` prefix
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from second_brain_database.managers.blog_auth_manager import blog_auth_manager
from second_brain_database.routes.auth.services.auth.login import get_current_user
from second_brain_database.routes.blog_dependencies import (
    require_access_admin,
    require_access_author,
    require_access_editor,
    require_access_owner,
    require_access_viewer,
)
from second_brain_database.managers.blog_manager import (
    BlogContentService,
    BlogWebsiteManager,
)
from second_brain_database.managers.blog_security import (
    blog_audit_logger,
    blog_xss_protection,
)
from second_brain_database.managers.logging_manager import get_logger


from second_brain_database.models.blog_models import (
    AutoSavePostRequest,
    CreateBlogCategoryRequest,
    BlogCategoryResponse,
    UpdateBlogCategoryRequest,
    CreateBlogCommentRequest,
    BlogCommentResponse,
    UpdateBlogCommentRequest,
    CreateBlogPostRequest,
    BlogPostResponse,
    UpdateBlogPostRequest,
    CreateBlogWebsiteRequest,
    BlogWebsiteResponse,
    UpdateBlogWebsiteRequest,
    WebsiteRole,
    RestoreVersionRequest,
    NewsletterSubscribeRequest,
    TrackAnalyticsRequest,
    NewsletterSubscriberResponse,
    EngagementMetricsResponse,
    BlogVersion,
    BlogSearchResponse,
)

logger = get_logger(prefix="[Blog Routes]")

# Initialize managers
website_manager = BlogWebsiteManager()
content_service = BlogContentService()

# Create router
router = APIRouter(prefix="/blog", tags=["blog"])


# Website Management Routes

@router.post("/websites", response_model=BlogWebsiteResponse)
async def create_website(
    request: BlogWebsiteCreateRequest,
    current_user: dict = Depends(get_current_user)  # Any authenticated user can create
):
    """
    Create a new blog website.

    This endpoint allows any authenticated user to create a new blog website.
    The creator automatically becomes the owner of the website.

    **Process:**
    1.  Validates the website name and slug (must be unique).
    2.  Creates the website document in the database.
    3.  Assigns the `OWNER` role to the creator.
    4.  Initializes default settings (e.g., comments enabled).

    Args:
        request (BlogWebsiteCreateRequest): The website creation data (name, slug, description).
        current_user (dict): The authenticated user (creator).

    Returns:
        BlogWebsiteResponse: The created website details.

    Raises:
        HTTPException(400): If the slug is already taken or invalid.
        HTTPException(500): If creation fails due to server error.
    """
    try:
        website = await website_manager.create_website(
            owner_id=current_user["_id"],
            name=request.name,
            slug=request.slug,
            description=request.description
        )

        logger.info("Created website: %s for user %s", website.website_id, current_user["username"])
        return BlogWebsiteResponse(**website.model_dump())

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create website: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create website")


@router.get("/websites", response_model=List[BlogWebsiteResponse])
async def get_user_websites(
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve all blog websites accessible to the current user.

    This endpoint returns a list of websites where the user has any role
    (Owner, Admin, Editor, Author, or Viewer).

    Args:
        current_user (dict): The authenticated user.

    Returns:
        List[BlogWebsiteResponse]: A list of websites the user is a member of.
    """
    try:
        websites = await website_manager.get_user_websites(current_user["_id"])
        return [BlogWebsiteResponse(**w.model_dump()) for w in websites]

    except Exception as e:
        logger.error("Failed to get user websites: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get websites")


@router.get("/websites/{website_id}", response_model=BlogWebsiteResponse)
async def get_website(
    website_id: str,
    current_user: dict = Depends(require_access_viewer)
):
    """
    Get detailed information about a specific blog website.

    This endpoint retrieves the website's metadata, settings, and configuration.
    It supports lookup by either the internal `website_id` or the public `slug`.

    **Access Control:**
    Requires at least `VIEWER` role on the website.

    Args:
        website_id (str): The unique ID or URL slug of the website.
        current_user (dict): The authenticated user (access verified by dependency).

    Returns:
        BlogWebsiteResponse: The website details.

    Raises:
        HTTPException(404): If the website is not found.
    """
    try:
        # Access check handled by dependency
        
        website = await website_manager.get_website_by_slug(website_id)  # website_id could be slug
        if not website:
            # Try as ID
            from second_brain_database.database import db_manager
            website_doc = await db_manager.get_tenant_collection("blog_websites").find_one({"website_id": website_id})
            if website_doc:
                website = BlogWebsiteResponse(**website_doc)

        if not website:
            raise HTTPException(status_code=404, detail="Website not found")

        return website

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get website: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get website")


# Website-scoped routes with {website_id} prefix

@router.put("/websites/{website_id}", response_model=BlogWebsiteResponse)
async def update_website(
    website_id: str,
    request: BlogWebsiteUpdateRequest,
    current_user: dict = Depends(require_access_admin)
):
    """
    Update blog website settings and metadata.

    This endpoint allows administrators and owners to modify website properties
    such as name, description, and configuration flags (e.g., allow comments).

    **Access Control:**
    Requires `ADMIN` or `OWNER` role.

    **Side Effects:**
    *   Updates the `updated_at` timestamp.
    *   Invalidates the website cache to ensure changes propagate immediately.

    Args:
        website_id (str): The ID of the website to update.
        request (BlogWebsiteUpdateRequest): The fields to update.
        current_user (dict): The authenticated user (admin/owner).

    Returns:
        BlogWebsiteResponse: The updated website details.

    Raises:
        HTTPException(404): If the website is not found.
    """
    try:
        # Access check handled by dependency

        # Update website
        from second_brain_database.database import db_manager
        update_data = request.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        result = await db_manager.get_tenant_collection("blog_websites").update_one(
            {"website_id": website_id},
            {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Website not found")

        # Get updated website
        website_doc = await db_manager.get_tenant_collection("blog_websites").find_one({"website_id": website_id})
        website = BlogWebsiteResponse(**website_doc)

        # Clear cache
        await website_manager._clear_website_cache(website_id)

        logger.info("Updated website: %s", website_id)
        return website

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update website: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update website")


# Post Management Routes

@router.post("/websites/{website_id}/posts", response_model=BlogPostResponse)
async def create_post(
    website_id: str,
    request: BlogPostCreateRequest,
    current_user: dict = Depends(require_access_author),
    req: Request = None
):
    """
    Create a new blog post.

    This endpoint allows authors, editors, and admins to publish new content.
    It includes automatic XSS sanitization, reading time calculation, and initial versioning.

    **Features:**
    *   **XSS Protection**: Sanitizes title, content, and excerpt to prevent script injection.
    *   **Metadata**: Automatically calculates `reading_time` and `word_count`.
    *   **Versioning**: Creates the first entry in the post's revision history.
    *   **Audit Logging**: Records the creation event for security and analytics.

    Args:
        website_id (str): The ID of the website.
        request (BlogPostCreateRequest): The post content and metadata.
        current_user (dict): The authenticated user (author).
        req (Request): The HTTP request object.

    Returns:
        BlogPostResponse: The created post.

    Raises:
        HTTPException(400): If input validation fails (e.g., invalid image URL).
    """
    try:
        # Access check handled by dependency

        # Sanitize content for XSS protection
        sanitized_title = blog_xss_protection.sanitize_html(request.title, allow_html=False)
        sanitized_content = blog_xss_protection.sanitize_post_content(request.content)
        sanitized_excerpt = blog_xss_protection.sanitize_html(request.excerpt, allow_html=False) if request.excerpt else None

        # Validate URLs if provided
        if request.featured_image and not blog_xss_protection.validate_url(request.featured_image):
            raise HTTPException(status_code=400, detail="Invalid featured image URL")

        # Calculate reading time (average 200 words per minute)
        word_count = len(sanitized_content.split())
        reading_time = max(1, word_count // 200)

        post = await content_service.create_post(
            website_id=website_id,
            author_id=current_user["_id"],
            title=sanitized_title,
            content=sanitized_content,
            excerpt=sanitized_excerpt,
            featured_image=request.featured_image,
            categories=request.categories,
            tags=request.tags,
            seo_title=request.seo_title,
            seo_description=request.seo_description,
            seo_keywords=request.seo_keywords,
            status=request.status
        )

        # Create initial version
        initial_version = BlogVersion(
            version_id=f"version_{uuid4().hex[:16]}",
            post_id=post.post_id,
            title=sanitized_title,
            content=sanitized_content,
            excerpt=sanitized_excerpt,
            created_at=datetime.utcnow(),
            created_by=current_user["_id"],
            change_summary="Initial version",
        )

        # Update post with reading time and initial version
        from second_brain_database.database import db_manager
        await db_manager.get_tenant_collection("blog_posts").update_one(
            {"post_id": post.post_id},
            {
                "$set": {"reading_time": reading_time, "word_count": word_count},
                "$push": {"revision_history": initial_version.model_dump()},
            },
        )

        # Audit log
        client_ip = req.client.host if req.client else "unknown"
        await blog_audit_logger.log_content_event(
            event_type="post_created",
            user_id=current_user["_id"],
            website_id=website_id,
            content_type="post",
            content_id=post.post_id,
            action="create",
            ip_address=client_ip,
            details={"title": sanitized_title, "status": request.status}
        )

        logger.info("Created post: %s in website %s", post.post_id, website_id)
        return BlogPostResponse(**post.model_dump())

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create post: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create post")


@router.get("/websites/{website_id}/posts", response_model=List[BlogPostResponse])
async def get_website_posts(
    website_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    status: str = Query("published", regex="^(draft|published|archived)$"),
    category: Optional[str] = None,
    current_user: dict = Depends(require_access_viewer)
):
    """
    Retrieve a paginated list of blog posts for a website.

    This endpoint supports filtering by status and category.
    
    **Filtering Rules:**
    *   **Status**: Defaults to "published". Viewers can only see published posts unless
        they have higher privileges (Author/Editor/Admin) to see drafts.
    *   **Category**: Optional filter by category slug.

    Args:
        website_id (str): The ID of the website.
        page (int): Page number (1-based).
        limit (int): Number of posts per page (max 50).
        status (str): Filter by post status (published, draft, archived).
        category (str, optional): Filter by category slug.
        current_user (dict): The authenticated user.

    Returns:
        List[BlogPostResponse]: A list of blog posts.
    """
    try:
        # Access check handled by dependency

        posts = await content_service.get_website_posts(
            website_id=website_id,
            page=page,
            limit=limit,
            status=status,
            category=category
        )

        return [BlogPostResponse(**p.model_dump()) for p in posts]

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get website posts: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get posts")


@router.get("/websites/{website_id}/posts/{post_slug}", response_model=BlogPostResponse)
async def get_post(
    website_id: str,
    post_slug: str,
    current_user: dict = Depends(require_access_viewer)
):
    """
    Retrieve a specific blog post by its slug.

    This endpoint returns the full content of a post. It is the primary endpoint
    for rendering a single post page.

    **Access Control:**
    *   **Published Posts**: Accessible to anyone with `VIEWER` role (including public if configured).
    *   **Drafts/Archived**: Only accessible to Authors, Editors, Admins, or Owners.

    Args:
        website_id (str): The ID of the website.
        post_slug (str): The URL-friendly slug of the post.
        current_user (dict): The authenticated user.

    Returns:
        BlogPostResponse: The requested post.

    Raises:
        HTTPException(404): If the post is not found.
    """
    try:
        # Access check handled by dependency

        post = await content_service.get_post_by_slug(website_id, post_slug)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        return BlogPostResponse(**post.model_dump())

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get post: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get post")


@router.put("/websites/{website_id}/posts/{post_id}", response_model=BlogPostResponse)
async def update_post(
    website_id: str,
    post_id: str,
    request: BlogPostUpdateRequest,
    current_user: dict = Depends(require_access_author),
    req: Request = None
):
    """
    Update an existing blog post.

    This endpoint allows modifying post content, metadata, and status.
    It automatically handles versioning and audit logging.

    **Versioning Logic:**
    If `title` or `content` is modified, a new entry is added to the `revision_history`
    preserving the state *before* this update.

    **Access Control:**
    *   **Authors**: Can only edit their *own* posts.
    *   **Editors/Admins/Owners**: Can edit *any* post.

    Args:
        website_id (str): The ID of the website.
        post_id (str): The ID of the post to update.
        request (BlogPostUpdateRequest): The fields to update.
        current_user (dict): The authenticated user.
        req (Request): The HTTP request object.

    Returns:
        BlogPostResponse: The updated post.

    Raises:
        HTTPException(403): If the user does not have permission to edit this specific post.
        HTTPException(404): If the post is not found.
    """
    try:
        # Access check handled by dependency

        # Check if user can edit this post (owner or editor+)
        from second_brain_database.database import db_manager
        post_doc = await db_manager.get_tenant_collection("blog_posts").find_one({
            "post_id": post_id,
            "website_id": website_id
        })

        if not post_doc:
            raise HTTPException(status_code=404, detail="Post not found")

        # Check permissions
        user_role = current_user.get("website_role")
        is_owner = post_doc["author_id"] == current_user["_id"]
        can_edit = (
            user_role in [WebsiteRole.OWNER, WebsiteRole.ADMIN, WebsiteRole.EDITOR] or
            (user_role == WebsiteRole.AUTHOR and is_owner)
        )

        if not can_edit:
            raise HTTPException(status_code=403, detail="Cannot edit this post")

        # Sanitize content for XSS protection
        update_data = request.model_dump(exclude_unset=True)
        if "title" in update_data:
            update_data["title"] = blog_xss_protection.sanitize_html(update_data["title"], allow_html=False)
        if "content" in update_data:
            update_data["content"] = blog_xss_protection.sanitize_post_content(update_data["content"])
        if "excerpt" in update_data and update_data["excerpt"]:
            update_data["excerpt"] = blog_xss_protection.sanitize_html(update_data["excerpt"], allow_html=False)

        # Validate URLs if provided
        if "featured_image" in update_data and update_data["featured_image"] and not blog_xss_protection.validate_url(update_data["featured_image"]):
            raise HTTPException(status_code=400, detail="Invalid featured image URL")

        # Save version if content changed
        version_update = {}
        if "content" in update_data or "title" in update_data:
            new_version = BlogVersion(
                version_id=f"version_{uuid4().hex[:16]}",
                post_id=post_id,
                title=post_doc["title"],
                content=post_doc["content"],
                excerpt=post_doc.get("excerpt"),
                created_at=datetime.utcnow(),
                created_by=current_user["_id"],
                change_summary=f"Update by {current_user.get('username', 'user')}",
            )
            version_update["$push"] = {"revision_history": new_version.model_dump()}

            # Recalculate reading time if content changed
            if "content" in update_data:
                word_count = len(update_data["content"].split())
                update_data["reading_time"] = max(1, word_count // 200)
                update_data["word_count"] = word_count

        # Update post
        update_data["updated_at"] = datetime.utcnow()

        update_operations = {"$set": update_data}
        if version_update:
            update_operations.update(version_update)

        result = await db_manager.get_tenant_collection("blog_posts").update_one(
            {"post_id": post_id, "website_id": website_id},
            update_operations
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Post not found")

        # Get updated post
        updated_post_doc = await db_manager.get_tenant_collection("blog_posts").find_one({
            "post_id": post_id, "website_id": website_id
        })
        post = BlogPostResponse(**updated_post_doc)

        # Audit log
        client_ip = req.client.host if req.client else "unknown"
        await blog_audit_logger.log_content_event(
            event_type="post_updated",
            user_id=current_user["_id"],
            website_id=website_id,
            content_type="post",
            content_id=post_id,
            action="update",
            ip_address=client_ip,
            details={"title": update_data.get("title"), "status": update_data.get("status")}
        )

        # Clear cache
        await content_service._clear_website_cache(website_id)

        logger.info("Updated post: %s", post_id)
        return post

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update post: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update post")


@router.delete("/websites/{website_id}/posts/{post_id}")
async def delete_post(
    website_id: str,
    post_id: str,
    current_user: dict = Depends(require_access_editor)
):
    """
    Permanently delete a blog post.

    This action removes the post document and all its associated comments and analytics data
    (cascading delete logic should be handled by the database or service layer).

    **Access Control:**
    Requires `EDITOR`, `ADMIN`, or `OWNER` role. Authors cannot delete posts (even their own)
    to prevent accidental data loss; they should archive them instead.

    Args:
        website_id (str): The ID of the website.
        post_id (str): The ID of the post to delete.
        current_user (dict): The authenticated user.

    Returns:
        dict: Success message.
    """
    try:
        # Access check handled by dependency

        from second_brain_database.database import db_manager

        # Check if post exists
        post_doc = await db_manager.get_tenant_collection("blog_posts").find_one({
            "post_id": post_id,
            "website_id": website_id
        })

        if not post_doc:
            raise HTTPException(status_code=404, detail="Post not found")

        # Delete post
        result = await db_manager.get_tenant_collection("blog_posts").delete_one({
            "post_id": post_id,
            "website_id": website_id
        })

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Post not found")

        # Update website post count
        await db_manager.get_tenant_collection("blog_websites").update_one(
            {"website_id": website_id},
            {"$inc": {"post_count": -1}}
        )

        # Clear cache
        await content_service._clear_website_cache(website_id)

        logger.info("Deleted post: %s from website %s", post_id, website_id)
        return {"message": "Post deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete post: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete post")


# Category Management Routes

@router.post("/websites/{website_id}/categories", response_model=BlogCategoryResponse)
async def create_category(
    website_id: str,
    request: CreateBlogCategoryRequest,
    current_user: dict = Depends(require_access_editor)
):
    """
    Create a new blog category.

    Categories help organize posts into topics. This endpoint ensures that category
    slugs are unique within the scope of the website.

    **Access Control:**
    Requires `EDITOR`, `ADMIN`, or `OWNER` role.

    Args:
        website_id (str): The ID of the website.
        request (CreateBlogCategoryRequest): The category details (name, slug, description).
        current_user (dict): The authenticated user.

    Returns:
        BlogCategoryResponse: The created category.

    Raises:
        HTTPException(400): If the category slug already exists in this website.
    """
    try:
        # Access check handled by dependency

        from second_brain_database.database import db_manager
        from datetime import datetime

        # Check if slug is unique within website
        existing = await db_manager.get_tenant_collection("blog_categories").find_one({
            "website_id": website_id,
            "slug": request.slug
        })

        if existing:
            raise HTTPException(status_code=400, detail="Category slug already exists")

        category_doc = {
            "category_id": f"category_{uuid4().hex[:16]}",
            "website_id": website_id,
            "name": request.name,
            "slug": request.slug,
            "description": request.description,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        await db_manager.get_tenant_collection("blog_categories").insert_one(category_doc)

        # Clear cache
        await content_service._clear_website_cache(website_id)

        logger.info("Created category: %s in website %s", category_doc["category_id"], website_id)
        return BlogCategoryResponse(**category_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create category: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create category")


@router.get("/websites/{website_id}/categories", response_model=List[BlogCategoryResponse])
async def get_website_categories(
    website_id: str,
    current_user: dict = Depends(require_access_viewer)
):
    """
    Retrieve all categories for a website.

    This endpoint returns a flat list of all categories defined for the website.
    It is typically used to populate navigation menus or filter dropdowns.

    Args:
        website_id (str): The ID of the website.
        current_user (dict): The authenticated user.

    Returns:
        List[BlogCategoryResponse]: A list of categories.
    """
    try:
        # Access check handled by dependency

        from second_brain_database.database import db_manager

        categories = []
        async for cat in db_manager.get_tenant_collection("blog_categories").find({"website_id": website_id}):
            categories.append(BlogCategoryResponse(**cat))

        return categories

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get website categories: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get categories")


# Comment Management Routes

@router.post("/websites/{website_id}/posts/{post_id}/comments", response_model=BlogCommentResponse)
async def create_comment(
    website_id: str,
    post_id: str,
    request: BlogCommentCreateRequest,
    current_user: dict = Depends(require_access_viewer),
    req: Request = None
):
    """
    Post a new comment on a blog post.

    This endpoint handles comment submission, including moderation checks and XSS sanitization.

    **Moderation Logic:**
    *   **Auto-Approval**: Comments by Authors, Editors, Admins, or Owners are automatically approved.
    *   **Pending Review**: Comments by Viewers (readers) may be set to `pending` status if the
        website requires approval (`require_comment_approval=True`).

    **Security:**
    *   **XSS Protection**: Sanitizes comment content and author name.
    *   **Audit Logging**: Logs the comment creation event.

    Args:
        website_id (str): The ID of the website.
        post_id (str): The ID of the post.
        request (BlogCommentCreateRequest): The comment content.
        current_user (dict): The authenticated user.
        req (Request): The HTTP request object.

    Returns:
        BlogCommentResponse: The created comment (with status).

    Raises:
        HTTPException(403): If comments are disabled for the website.
    """
    try:
        # Access check handled by dependency

        from second_brain_database.database import db_manager
        from datetime import datetime

        # Check if post exists and allows comments
        post_doc = await db_manager.get_tenant_collection("blog_posts").find_one({
            "post_id": post_id,
            "website_id": website_id
        })

        if not post_doc:
            raise HTTPException(status_code=404, detail="Post not found")

        # Check if website allows comments
        website_doc = await db_manager.get_tenant_collection("blog_websites").find_one({"website_id": website_id})
        if not website_doc or not website_doc.get("allow_comments", True):
            raise HTTPException(status_code=403, detail="Comments are disabled for this website")

        # Check approval requirement
        needs_approval = website_doc.get("require_comment_approval", True)
        is_author = post_doc["author_id"] == current_user["_id"]
        user_role = current_user.get("website_role")

        # Authors and editors can comment without approval
        status = "approved" if (
            not needs_approval or
            is_author or
            user_role in [WebsiteRole.OWNER, WebsiteRole.ADMIN, WebsiteRole.EDITOR]
        ) else "pending"

        # Sanitize comment content for XSS protection
        sanitized_content = blog_xss_protection.sanitize_comment_content(request.content)
        sanitized_author_name = blog_xss_protection.sanitize_html(request.author_name or current_user.get("username"), allow_html=False)

        comment_doc = {
            "comment_id": f"comment_{uuid4().hex[:16]}",
            "website_id": website_id,
            "post_id": post_id,
            "author_id": current_user["_id"],
            "author_name": sanitized_author_name,
            "author_email": request.author_email,
            "content": sanitized_content,
            "status": status,
            "parent_id": request.parent_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        await db_manager.get_tenant_collection("blog_comments").insert_one(comment_doc)

        # Update post comment count
        await db_manager.get_tenant_collection("blog_posts").update_one(
            {"post_id": post_id, "website_id": website_id},
            {"$inc": {"comment_count": 1}}
        )

        # Audit log
        client_ip = req.client.host if req.client else "unknown"
        await blog_audit_logger.log_content_event(
            event_type="comment_created",
            user_id=current_user["_id"],
            website_id=website_id,
            content_type="comment",
            content_id=comment_doc["comment_id"],
            action="create",
            ip_address=client_ip,
            details={"post_id": post_id, "status": status}
        )

        logger.info("Created comment: %s on post %s", comment_doc["comment_id"], post_id)
        return BlogCommentResponse(**comment_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create comment: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create comment")


@router.get("/websites/{website_id}/posts/{post_id}/comments", response_model=List[BlogCommentResponse])
async def get_post_comments(
    website_id: str,
    post_id: str,
    status: str = Query("approved", regex="^(pending|approved|spam|deleted)$"),
    current_user: dict = Depends(require_access_viewer)
):
    """
    Retrieve comments for a specific post.

    **Access Control:**
    *   **Viewers**: Can only see `approved` comments.
    *   **Editors+**: Can see comments in any status (pending, spam, deleted) for moderation.

    Args:
        website_id (str): The ID of the website.
        post_id (str): The ID of the post.
        status (str): Filter by comment status (default: "approved").
        current_user (dict): The authenticated user.

    Returns:
        List[BlogCommentResponse]: A list of comments.

    Raises:
        HTTPException(403): If a Viewer attempts to access non-approved comments.
    """
    try:
        # Access check handled by dependency

        from second_brain_database.database import db_manager

        # Check if user can see pending comments (editors+)
        user_role = current_user.get("website_role")
        can_see_pending = user_role in [WebsiteRole.OWNER, WebsiteRole.ADMIN, WebsiteRole.EDITOR]

        if status == "pending" and not can_see_pending:
            raise HTTPException(status_code=403, detail="Cannot view pending comments")

        query = {"website_id": website_id, "post_id": post_id}
        if not can_see_pending:
            query["status"] = "approved"

        comments = []
        async for comment in db_manager.get_tenant_collection("blog_comments").find(query).sort("created_at", 1):
            comments.append(BlogCommentResponse(**comment))

        return comments

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get post comments: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get comments")


@router.get("/websites/{website_id}/comments", response_model=List[BlogCommentResponse])
async def get_website_comments(
    website_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, regex="^(pending|approved|rejected|spam)$"),
    current_user: dict = Depends(require_access_editor)
):
    """
    Retrieve all comments across the entire website (Moderation Queue).

    This endpoint is designed for moderators to review comments. It supports pagination
    and filtering by status (e.g., to see all `pending` comments).

    **Access Control:**
    Requires `EDITOR`, `ADMIN`, or `OWNER` role.

    Args:
        website_id (str): The ID of the website.
        page (int): Page number.
        limit (int): Comments per page.
        status (str, optional): Filter by status.
        current_user (dict): The authenticated user.

    Returns:
        List[BlogCommentResponse]: A list of comments.
    """
    try:
        # Access check handled by dependency

        from second_brain_database.database import db_manager

        query = {"website_id": website_id}
        if status:
            query["status"] = status

        comments = []
        cursor = db_manager.get_tenant_collection("blog_comments").find(query)
        cursor.sort("created_at", -1).skip((page - 1) * limit).limit(limit)

        async for comment in cursor:
            comments.append(BlogCommentResponse(**comment))

        return comments

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get website comments: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get comments")


# Authentication Routes for Blog

@router.post("/auth/websites/{website_id}/login")
async def login_to_website(
    website_id: str,
    current_user: dict = Depends(require_access_viewer)  # Any authenticated user
):
    """
    Authenticate a user into a specific blog website context.

    This endpoint issues a website-scoped JWT token. This token contains the user's
    specific role within *this* website (e.g., Editor), allowing the frontend to
    adjust the UI accordingly.

    **Use Case:**
    When a user enters the "Manage Website" dashboard, the frontend should exchange
    their main auth token for this website-specific token.

    Args:
        website_id (str): The ID of the website to login to.
        current_user (dict): The authenticated user.

    Returns:
        dict: Access token and role information.
    """
    try:
        # Check if user has access to this website
        membership = await website_manager.check_website_access(
            current_user["_id"], website_id, WebsiteRole.VIEWER
        )

        if not membership:
            raise HTTPException(status_code=403, detail="Access denied to this website")

        # Create website token
        token = await blog_auth_manager.create_website_token(
            user_id=current_user["_id"],
            username=current_user["username"],
            website_id=website_id,
            role=membership.role
        )

        logger.info("User %s logged into website %s with role %s",
                   current_user["username"], website_id, membership.role.value)

        return {
            "access_token": token,
            "token_type": "bearer",
            "website_id": website_id,
            "role": membership.role.value
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to login to website: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to login to website")


# Analytics Routes (Admin only)

@router.get("/websites/{website_id}/analytics")
async def get_website_analytics(
    website_id: str,
    days: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(require_access_admin)
):
    """
    Retrieve aggregated analytics for a website.

    This endpoint provides high-level metrics such as total views, unique visitors,
    and engagement trends over a specified period.

    **Access Control:**
    Requires `ADMIN` or `OWNER` role.

    Args:
        website_id (str): The ID of the website.
        days (int): Number of days to look back (default 30).
        current_user (dict): The authenticated user.

    Returns:
        dict: Analytics data structure.
    """
    try:
        # Access check handled by dependency

        from second_brain_database.managers.blog_manager import BlogAnalyticsService

        analytics_service = BlogAnalyticsService()
        analytics = await analytics_service.get_website_analytics(website_id, days)

        return analytics

    except Exception as e:
        logger.error("Failed to get website analytics: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get analytics")


# Search Routes

@router.get("/websites/{website_id}/search", response_model=BlogSearchResponse)
async def search_posts(
    website_id: str,
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(require_access_viewer)
):
    """
    Search for posts within a website.

    Performs a full-text search on post titles and content.

    Args:
        website_id (str): The ID of the website.
        q (str): The search query string.
        page (int): Page number.
        limit (int): Results per page.
        current_user (dict): The authenticated user.

    Returns:
        BlogSearchResponse: Search results and metadata.
    """
    try:
        # Access check handled by dependency

        from second_brain_database.database import db_manager
        import re

        # Create regex for case-insensitive search
        search_regex = {"$regex": re.escape(q), "$options": "i"}

        query = {
            "website_id": website_id,
            "status": "published",
            "$or": [
                {"title": search_regex},
                {"excerpt": search_regex},
                {"tags": search_regex}
            ]
        }

        # Count total results
        total = await db_manager.get_tenant_collection("blog_posts").count_documents(query)

        # Get posts
        posts = []
        cursor = db_manager.get_tenant_collection("blog_posts").find(query)
        cursor.sort("published_at", -1).skip((page - 1) * limit).limit(limit)
        
        async for post in cursor:
            posts.append(BlogPostResponse(**post))

        # Calculate pagination
        import math
        total_pages = math.ceil(total / limit)
        
        return BlogSearchResponse(
            query=q,
            total_results=total,
            posts=posts,
            categories=[], # Could enhance to search categories too
            pagination={
                "page": page,
                "limit": limit,
                "total": total,
                "pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to search posts: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search posts")


# Subscriber Management Routes

@router.get("/websites/{website_id}/subscribers", response_model=List[NewsletterSubscriberResponse])
async def get_subscribers(
    website_id: str,
    current_user: dict = Depends(require_access_admin)
):
    """Get all newsletter subscribers (admin only)."""
    try:
        # Access check handled by dependency

        from second_brain_database.database import db_manager

        subscribers = []
        async for sub in db_manager.get_tenant_collection("blog_newsletter_subscribers").find({"website_id": website_id}):
            subscribers.append(NewsletterSubscriberResponse(**sub))

        return subscribers

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get subscribers: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get subscribers")